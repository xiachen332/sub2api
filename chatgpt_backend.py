# -*- coding: utf-8 -*-

"""
ChatGPT Backend API Client (Fixed)

Correct endpoint: POST https://chatgpt.com/backend-api/codex/responses
Correct payload format:
{
    "model": "gpt-5.4",
    "input": [{"role": "user", "content": [{"type": "input_text", "text": "..."}]}],
    "instructions": "You are a helpful assistant.",
    "store": False,
    "stream": True
}
SSE format: event: xxx\ndata: xxx\n\n
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, AsyncGenerator
import httpx
import logging

logger = logging.getLogger("sub2api.backend")


class ChatGPTBackend:
    """Client for ChatGPT backend API (codex/responses endpoint)."""
    
    CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"
    
    DEFAULT_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    def _build_headers(self, access_token: str, account_id: str = "") -> Dict[str, str]:
        headers = {
            **self.DEFAULT_HEADERS,
            "Authorization": f"Bearer {access_token}",
        }
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id
        return headers
    
    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool = True,
    ) -> Dict[str, Any]:
        """Build Codex-style request payload."""
        
        # Extract system prompt from messages
        instructions = "You are a helpful assistant."
        
        # Build input (not messages!)
        codex_input = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Skip system messages (they go into instructions)
            if role == "system":
                if isinstance(content, str):
                    instructions = content
                elif isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    instructions = "\n".join(text_parts)
                continue
            
            # Convert content to parts format
            if isinstance(content, str):
                content_parts = [{"type": "input_text", "text": content}]
            elif isinstance(content, list):
                content_parts = []
                for part in content:
                    if not isinstance(part, dict):
                        content_parts.append(part)
                        continue
                        
                    part_type = part.get("type", "")
                    if part_type == "text":
                        content_parts.append({"type": "input_text", "text": part.get("text", "")})
                    elif part_type == "image_url":
                        # Convert OpenAI image_url to backend input_image
                        image_url = part.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                        content_parts.append({"type": "input_image", "image_url": url})
                    elif part_type == "input_image":
                        # Already in backend format
                        content_parts.append(part)
                    else:
                        content_parts.append(part)
            else:
                content_parts = [{"type": "input_text", "text": str(content)}]
            
            codex_input.append({
                "role": role,
                "content": content_parts,
            })
        
        return {
            "model": model,
            "input": codex_input,
            "instructions": instructions,
            "store": False,
            "stream": stream,
        }
    
    async def chat_completions(
        self,
        access_token: str,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        account_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Send chat completion to ChatGPT backend-api/codex/responses.
        
        Yields SSE chunks (OpenAI-compatible format).
        """
        
        logger.info(f"Backend-api request: model={model}")
        
        headers = self._build_headers(access_token, account_id)
        payload = self._build_payload(messages, model, True)
        
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(datetime.now(timezone.utc).timestamp())
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                        yield self._build_error_sse(request_id, created, model, f"HTTP {response.status_code}: {error_text}")
                        return
                    
                    # Parse SSE response (event: xxx\ndata: xxx\n\n format)
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            event_data = self._parse_sse_event(event_str)
                            
                            if event_data:
                                openai_chunk = self._convert_to_openai_format(
                                    event_data, request_id, created, model
                                )
                                if openai_chunk:
                                    yield f"data: {json.dumps(openai_chunk)}\n\n"
                    
                    # Send finish chunk
                    yield f"data: {json.dumps(self._build_finish_chunk(request_id, created, model))}\n\n"
                    yield "data: [DONE]\n\n"
                    
        except Exception as e:
            logger.error(f"Request error: {e}")
            yield self._build_error_sse(request_id, created, model, str(e))
    
    def _parse_sse_event(self, event_str: str) -> Optional[Dict[str, Any]]:
        """Parse SSE event string (event: xxx\ndata: xxx)."""
        lines = event_str.strip().split("\n")
        event_type = ""
        data_content = ""
        
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_content = line[6:].strip()
        
        if not data_content:
            return None
        
        try:
            data = json.loads(data_content)
            data["_event_type"] = event_type
            return data
        except json.JSONDecodeError:
            return {"_event_type": event_type, "type": "text", "text": data_content}
    
    def _convert_to_openai_format(
        self,
        data: Dict[str, Any],
        request_id: str,
        created: int,
        model: str,
    ) -> Optional[Dict[str, Any]]:
        """Convert Codex event to OpenAI streaming format."""
        
        # Handle text delta
        if data.get("type") == "response.output_text.delta":
            delta_text = data.get("delta", "")
            if not delta_text:
                return None
            
            return {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": delta_text},
                        "finish_reason": None,
                    }
                ],
            }
        
        # Handle message event
        if data.get("_event_type") == "message":
            msg_type = data.get("type", "")
            if msg_type == "response.output_text.delta":
                return self._convert_to_openai_format(data, request_id, created, model)
            elif msg_type == "response.completed":
                return self._build_finish_chunk(request_id, created, model)
        
        # Handle text events
        if data.get("type") == "text":
            text = data.get("text", "")
            if text:
                return {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": text},
                            "finish_reason": None,
                        }
                    ],
                }
        
        return None
    
    def _build_finish_chunk(self, request_id: str, created: int, model: str) -> Dict[str, Any]:
        """Build finish chunk."""
        return {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
    
    async def responses(
        self,
        access_token: str,
        input_data: List[Dict[str, Any]],
        model: str,
        instructions: Optional[str] = None,
        stream: bool = True,
        store: bool = False,
        account_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Send request to ChatGPT backend-api/codex/responses (Responses API format).
        
        Yields SSE chunks (Responses API format).
        """
        
        logger.info(f"Responses API request: model={model}")
        
        headers = self._build_headers(access_token, account_id)
        
        # Convert input to backend format
        codex_input = []
        for item in input_data:
            role = item.get("role", "user")
            content = item.get("content", "")
            
            if isinstance(content, str):
                content_parts = [{"type": "input_text", "text": content}]
            elif isinstance(content, list):
                content_parts = []
                for part in content:
                    if not isinstance(part, dict):
                        content_parts.append(part)
                        continue
                        
                    part_type = part.get("type", "")
                    if part_type == "text":
                        content_parts.append({"type": "input_text", "text": part.get("text", "")})
                    elif part_type == "image_url":
                        image_url = part.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                        content_parts.append({"type": "input_image", "image_url": url})
                    elif part_type == "input_image":
                        content_parts.append(part)
                    else:
                        content_parts.append(part)
            else:
                content_parts = [{"type": "input_text", "text": str(content)}]
            
            codex_input.append({
                "role": role,
                "content": content_parts,
            })
        
        payload: Dict[str, Any] = {
            "model": model,
            "input": codex_input,
            "instructions": instructions or "You are a helpful assistant.",
            "store": store,
            "stream": stream,
        }
        
        if instructions:
            payload["instructions"] = instructions
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                        yield f"event: error\ndata: {json.dumps({'error': error_text})}\n\n"
                        return
                    
                    # Directly pass through SSE response
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            yield event_str + "\n\n"
                    
        except Exception as e:
            logger.error(f"Request error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    async def responses_raw(
        self,
        access_token: str,
        payload: Dict[str, Any],
        account_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Send raw request payload to ChatGPT backend-api/codex/responses.
        Passes through all fields (tools, reasoning, etc.) unchanged.
        
        Yields SSE chunks (pass-through format).
        """
        
        logger.info(f"Responses raw request: model={payload.get('model')}")
        
        headers = self._build_headers(access_token, account_id)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                        yield f"event: error\ndata: {json.dumps({'error': error_text})}\n\n"
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
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    def _build_error_sse(
        self,
        request_id: str,
        created: int,
        model: str,
        error: str,
    ) -> str:
        """Build error SSE."""
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": f"[Error: {error}]"},
                    "finish_reason": "stop",
                }
            ],
        }
        return f"data: {json.dumps(chunk)}\n\n"
