"""
Response Compatibility Layer

参考：Wei-Shaw/sub2api backend/internal/pkg/apicompat/
负责后端 API 响应和 OpenAI Responses API 格式之间的转换
"""

import json
import os
import asyncio
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("sub2api.compat.response")

class ResponseConverter:
    """Converts backend API responses to OpenAI Responses API format."""
    
    @staticmethod
    def build_streaming_response(
        backend_generator,
        model: str,
        account_manager,
        account
    ):
        """Build a StreamingResponse from backend SSE generator."""
        async def event_generator():
            try:
                async for chunk in backend_generator:
                    yield chunk
                
                await account_manager.report_success(account)
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await account_manager.report_error(account, str(e))
                raise
        
        return event_generator
    
    @staticmethod
    async def build_non_streaming_response(
        backend_generator,
        model: str,
        account_manager,
        account
    ) -> Dict[str, Any]:
        """
        Build a non-streaming JSON response from backend SSE events.
        
        Extracts content from SSE events and assembles into Responses API format.
        """
        logger.info("Processing non-streaming request")
        
        full_response = ""
        completed_response = None
        
        async for chunk in backend_generator:
            # Parse SSE events
            lines = chunk.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    data_str = line[6:].strip()
                    if data_str and data_str != '[DONE]':
                        try:
                            parsed = json.loads(data_str)
                            event_type = parsed.get('type', '')
                            
                            # Handle text delta
                            if event_type == 'response.output_text.delta':
                                full_response += parsed.get('delta', '')
                            
                            # Handle text events
                            elif event_type == 'text':
                                full_response += parsed.get('text', '')
                            
                            # Handle completion - extract full response
                            elif event_type == 'response.completed':
                                logger.info("Response completed event received")
                                if 'response' in parsed:
                                    completed_response = parsed['response']
                                    logger.info(f"Completed response has {len(completed_response.get('output', []))} output items")
                                break
                            
                            # Handle output item added
                            elif event_type == 'response.output_item.added':
                                logger.info(f"Output item added: {parsed.get('item', {}).get('type', 'unknown')}")
                                
                        except json.JSONDecodeError:
                            pass
        
        await account_manager.report_success(account)
        
        # If we have completed response with output, return it
        if completed_response and 'output' in completed_response:
            logger.info(f"Returning completed response with {len(completed_response['output'])} output items")
            
            response_data = {
                "id": completed_response.get('id', f"resp_{os.urandom(12).hex()}"),
                "object": "response",
                "created_at": completed_response.get('created_at', int(asyncio.get_event_loop().time())),
                "model": completed_response.get('model', model),
                "output": completed_response['output'],
                "status": completed_response.get('status', 'completed'),
            }
            
            # Include usage info (contains cache hit details)
            if 'usage' in completed_response:
                response_data['usage'] = completed_response['usage']
                usage = completed_response['usage']
                cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
                logger.info(f"Cache hit: {cached} tokens cached")
            
            return response_data
        
        # Fallback: build simple text output
        logger.info(f"Non-streaming response ready, length={len(full_response)}")
        return {
            "id": f"resp_{os.urandom(12).hex()}",
            "object": "response",
            "created_at": int(asyncio.get_event_loop().time()),
            "model": model,
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": full_response}],
                }
            ],
        }
