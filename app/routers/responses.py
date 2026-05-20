"""
Responses API Router

Handles /v1/responses endpoint
"""

import json
import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse

logger = logging.getLogger("sub2api.router.responses")
router = APIRouter()

def verify_api_key(auth_header: str, expected_key: str) -> bool:
    """Verify API key from Authorization header."""
    if not auth_header:
        return False
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == expected_key

@router.post("/responses")
async def responses_endpoint(request: Request):
    """OpenAI Responses API endpoint."""
    from app.config import API_KEY
    from app.main import gateway_service
    
    # Verify API key
    auth = request.headers.get("Authorization", "")
    if not verify_api_key(auth, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Parse request body
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Determine streaming mode
    client_stream = body.get("stream", True)
    
    try:
        if client_stream:
            # Streaming response
            generator = await gateway_service.handle_responses_request(body, stream=True)
            return StreamingResponse(
                generator,
                media_type="text/event-stream",
            )
        else:
            # Non-streaming response
            result = await gateway_service.handle_responses_request(body, stream=False)
            if isinstance(result, dict):
                return JSONResponse(content=result)
            else:
                return StreamingResponse(
                    result,
                    media_type="text/event-stream",
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/responses/{response_id}")
async def get_response(response_id: str):
    """Get a response by ID (not implemented yet)."""
    raise HTTPException(status_code=501, detail="Not implemented")

@router.delete("/responses/{response_id}")
async def delete_response(response_id: str):
    """Delete a response (not implemented yet)."""
    raise HTTPException(status_code=501, detail="Not implemented")
