"""
Gateway Service

参考：Wei-Shaw/sub2api backend/internal/service/gateway_service.go
核心网关服务，负责请求路由、转发、错误处理
"""

import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import HTTPException

from internal.service.account import AccountManager, Account
from internal.upstream.chatgpt import ChatGPTBackend
from internal.compat.request import RequestConverter
from internal.compat.response import ResponseConverter
from internal.compat.sse import SSEProcessor

logger = logging.getLogger("sub2api.gateway")

class GatewayService:
    """Core gateway service for API request handling."""
    
    def __init__(
        self,
        account_manager: AccountManager,
        backend: ChatGPTBackend,
        config: Optional[Dict[str, Any]] = None
    ):
        self.account_manager = account_manager
        self.backend = backend
        self.config = config or {}
    
    async def handle_responses_request(
        self,
        body: Dict[str, Any],
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Handle a /v1/responses request.
        
        1. Get account
        2. Convert request format
        3. Forward to backend
        4. Return response (streaming or buffered)
        """
        # Get account
        account = self.account_manager.get_account()
        if not account:
            raise HTTPException(status_code=503, detail="No healthy accounts available")
        
        logger.info(
            f"Responses request: model={body.get('model')}, "
            f"input={len(body.get('input', []))}, "
            f"stream={stream}, "
            f"account={account.email}"
        )
        
        # Convert request
        backend_payload = RequestConverter.convert_request(body)
        
        # Forward to backend
        backend_generator = self.backend.responses_raw(
            access_token=account.access_token,
            payload=backend_payload,
            account_id=account.account_id,
        )
        
        if stream:
            # Streaming response
            return ResponseConverter.build_streaming_response(
                backend_generator,
                body.get('model', 'gpt-5.5'),
                self.account_manager,
                account
            )
        else:
            # Non-streaming response
            result = await ResponseConverter.build_non_streaming_response(
                backend_generator,
                body.get('model', 'gpt-5.5'),
                self.account_manager,
                account
            )
            return result
    
    async def handle_chat_completions_request(
        self,
        body: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """Handle a /v1/chat/completions request."""
        # For now, forward to responses endpoint
        # TODO: Implement proper chat completions conversion
        return await self.handle_responses_request(body, stream=body.get('stream', True))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gateway statistics."""
        return {
            "version": "2.0.0",
            "accounts": self.account_manager.get_stats(),
        }
