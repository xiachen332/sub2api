"""
ChatGPT Backend API Client

参考：Wei-Shaw/sub2api backend/internal/service/openai_
负责连接 ChatGPT 网页版 API
"""

import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List
import httpx
import logging

logger = logging.getLogger("sub2api.upstream")

class ChatGPTBackend:
    """Client for ChatGPT web backend API."""
    
    CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"
    
    def __init__(self, timeout: float = 120.0):
        self.timeout = timeout
    
    def _build_headers(
        self,
        access_token: str,
        account_id: str = "",
    ) -> Dict[str, str]:
        """Build request headers with auth."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if account_id:
            headers["X-Account-ID"] = account_id
        return headers
    
    async def responses_raw(
        self,
        access_token: str,
        payload: Dict[str, Any],
        account_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Send raw request to ChatGPT backend.
        Passes through all fields unchanged.
        
        Yields SSE chunks.
        """
        logger.info(f"Responses raw request: model={payload.get('model')}")
        
        headers = self._build_headers(access_token, account_id)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.CODEX_API_URL,
                    headers=headers,
                    json=payload,
                ) as response:
                    
                    if response.status_code != 200:
                        error_text = ""
                        try:
                            error_text = (await response.aread()).decode()[:500]
                        except:
                            pass
                        logger.error(f"Backend error {response.status_code}: {error_text}")
                        yield SSEProcessor.build_sse_event("error", {"error": error_text})
                        return
                    
                    # Directly pass through SSE response
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            yield event_str + "\n\n"
                    
                    # Ensure any remaining data is yielded
                    if buffer.strip():
                        yield buffer.strip() + "\n\n"
                    
        except Exception as e:
            logger.error(f"Request error: {e}")
            yield SSEProcessor.build_sse_event("error", {"error": str(e)})
    
    async def responses(
        self,
        access_token: str,
        input_data: List[Dict[str, Any]],
        model: str,
        instructions: Optional[str] = None,
        stream: bool = True,
        store: bool = False,
        account_id: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send request to ChatGPT backend with simplified parameters.
        
        Yields SSE chunks.
        """
        payload = {
            "model": model,
            "input": input_data,
            "instructions": instructions or "You are a helpful assistant.",
            "store": store,
            "stream": True,  # Backend requires stream=True
        }
        
        if tools:
            payload["tools"] = tools
        
        async for chunk in self.responses_raw(access_token, payload, account_id):
            yield chunk
