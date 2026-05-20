# -*- coding: utf-8 -*-

"""
Sub2API - Simplified ChatGPT Backend API Proxy

OpenAI-compatible API server using ChatGPT web accounts.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from config import HOST, PORT, API_KEY, ACCOUNTS_FILE, AVAILABLE_MODELS
from account_manager import AccountManager
from chatgpt_backend import ChatGPTBackend

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sub2api")


# Global state
account_manager: Optional[AccountManager] = None
backend: Optional[ChatGPTBackend] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global account_manager, backend
    
    logger.info("=" * 50)
    logger.info("Sub2API Starting...")
    logger.info("=" * 50)
    
    # Initialize account manager
    accounts_path = ACCOUNTS_FILE
    if not os.path.isabs(accounts_path):
        accounts_path = os.path.join(os.path.dirname(__file__), accounts_path)
    
    account_manager = AccountManager(accounts_path)
    backend = ChatGPTBackend()
    
    healthy = account_manager.get_healthy_count()
    total = len(account_manager.accounts)
    
    logger.info(f"Loaded {total} accounts, {healthy} healthy")
    logger.info(f"API Key: {API_KEY[:8]}...")
    logger.info(f"Server: http://{HOST}:{PORT}")
    logger.info("Ready!")
    
    yield
    
    logger.info("Shutting down Sub2API...")


app = FastAPI(
    title="Sub2API",
    description="OpenAI-compatible API for ChatGPT web accounts",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(authorization: Optional[str]) -> bool:
    """Verify API key from Authorization header."""
    if not API_KEY:
        return True
    
    if not authorization:
        return False
    
    # Extract key from "Bearer xxx" or just "xxx"
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1] == API_KEY
    elif len(parts) == 1:
        return parts[0] == API_KEY
    
    return False


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Sub2API",
        "version": "1.0.0",
        "status": "running",
        "accounts": {
            "total": len(account_manager.accounts) if account_manager else 0,
            "healthy": account_manager.get_healthy_count() if account_manager else 0,
        },
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Web dashboard for Sub2API."""
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return "<h1>Sub2API Dashboard</h1><p>dashboard.html not found</p>"


@app.get("/health")
async def health():
    """Health check endpoint."""
    healthy = account_manager.get_healthy_count() if account_manager else 0
    total = len(account_manager.accounts) if account_manager else 0
    
    return {
        "status": "healthy" if healthy > 0 else "unhealthy",
        "accounts": {
            "total": total,
            "healthy": healthy,
        },
    }


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    return {
        "object": "list",
        "data": AVAILABLE_MODELS,
    }


@app.get("/accounts")
async def list_accounts(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """List all accounts (admin endpoint)."""
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return account_manager.get_stats() if account_manager else {"total": 0}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Chat completions endpoint (OpenAI-compatible)."""
    # Verify API key
    auth = request.headers.get("Authorization", "")
    if not verify_api_key(auth):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Parse request body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o")
    stream = body.get("stream", False)
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")
    
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    
    # Get account
    account = await account_manager.get_account()
    if not account:
        raise HTTPException(status_code=503, detail="No healthy accounts available")
    
    logger.info(f"Request: model={model}, messages={len(messages)}, account={account.email or account.name}")
    
    try:
        if stream:
            # Streaming response
            async def event_generator():
                try:
                    async for chunk in backend.chat_completions(
                        access_token=account.access_token,
                        messages=messages,
                        model=model,
                        stream=True,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        account_id=account.account_id,
                    ):
                        yield chunk
                    
                    await account_manager.report_success(account)
                    
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    await account_manager.report_error(account, str(e))
                    raise
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )
        
        else:
            # Non-streaming response
            full_text = ""
            async for chunk in backend.chat_completions(
                access_token=account.access_token,
                messages=messages,
                model=model,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
                account_id=account.account_id,
            ):
                # Parse the data: line
                if chunk.startswith("data: "):
                    data = chunk[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        if "choices" in parsed and parsed["choices"]:
                            delta = parsed["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            full_text += content
                    except:
                        pass
            
            await account_manager.report_success(account)
            
            return {
                "id": f"chatcmpl-{os.urandom(6).hex()}",
                "object": "chat.completion",
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": full_text,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request failed: {e}")
        await account_manager.report_error(account, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/responses")
async def responses_endpoint(request: Request):
    """Responses API endpoint (OpenAI Responses API compatible)."""
    # Verify API key
    auth = request.headers.get("Authorization", "")
    if not verify_api_key(auth):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Parse request body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    input_data = body.get("input", [])
    model = body.get("model", "gpt-5.5")
    stream = body.get("stream", True)
    instructions = body.get("instructions")
    store = body.get("store", False)
    
    if not input_data:
        raise HTTPException(status_code=400, detail="No input provided")
    
    # Get account
    account = await account_manager.get_account()
    if not account:
        raise HTTPException(status_code=503, detail="No healthy accounts available")
    
    logger.info(f"Responses request: model={model}, input={len(input_data)}, account={account.email or account.name}")
    
    try:
        if stream:
            # Streaming response (pass through SSE directly)
            async def event_generator():
                try:
                    async for chunk in backend.responses(
                        access_token=account.access_token,
                        input_data=input_data,
                        model=model,
                        stream=True,
                        instructions=instructions,
                        store=store,
                        account_id=account.account_id,
                    ):
                        yield chunk
                    
                    await account_manager.report_success(account)
                    
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    await account_manager.report_error(account, str(e))
                    raise
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )
        
        else:
            # Non-streaming response (collect all SSE content)
            full_response = ""
            async for chunk in backend.responses(
                access_token=account.access_token,
                input_data=input_data,
                model=model,
                stream=True,  # Backend always requires stream=True
                instructions=instructions,
                store=store,
                account_id=account.account_id,
            ):
                # Parse SSE events to extract content
                lines = chunk.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:].strip()
                        if data_str and data_str != '[DONE]':
                            try:
                                parsed = json.loads(data_str)
                                if parsed.get('type') == 'response.output_text.delta':
                                    full_response += parsed.get('delta', '')
                                elif parsed.get('type') == 'text':
                                    full_response += parsed.get('text', '')
                            except:
                                pass
            
            await account_manager.report_success(account)
            
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
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request failed: {e}")
        await account_manager.report_error(account, str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _convert_input_for_backend(body: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI input format to backend format."""
    backend_payload = dict(body)
    
    # Convert input content types
    if "input" in backend_payload and isinstance(backend_payload["input"], list):
        codex_input = []
        for item in backend_payload["input"]:
            if not isinstance(item, dict):
                codex_input.append(item)
                continue
            
            # Handle special item types (e.g., function_call_output without role/content)
            item_type = item.get("type", "")
            if item_type == "function_call_output":
                # Convert function_call_output to a system message with input_text
                call_id = item.get("call_id", "")
                output = item.get("output", "")
                codex_input.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Tool call {call_id} result:\n{output}"}]
                })
                continue
            elif item_type == "tool_result":
                # Convert tool_result to a system message with input_text
                tool_use_id = item.get("tool_use_id", "")
                result_content = item.get("content", "")
                codex_input.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Tool {tool_use_id} result:\n{result_content}"}]
                })
                continue
            
            # Normal message item with role and content
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
                        # Convert OpenAI image_url format to backend input_image format
                        image_url = part.get("image_url", {})
                        url = image_url.get("url", "") if isinstance(image_url, dict) else image_url
                        
                        if url.startswith("data:image"):
                            # Base64 encoded image: data:image/jpeg;base64,/9j/4AAQ...
                            # Extract mime type and base64 data
                            try:
                                header, base64_data = url.split(",", 1)
                                mime_type = header.split(";")[0].split(":")[1]
                                content_parts.append({
                                    "type": "input_image",
                                    "image_url": url,  # Keep original for backend compatibility
                                    "detail": image_url.get("detail", "auto") if isinstance(image_url, dict) else "auto",
                                })
                            except:
                                content_parts.append({"type": "input_image", "image_url": url})
                        else:
                            # Regular URL
                            content_parts.append({
                                "type": "input_image",
                                "image_url": url,
                                "detail": image_url.get("detail", "auto") if isinstance(image_url, dict) else "auto",
                            })
                    
                    elif part_type == "function_call_output":
                        # Convert function_call_output to input_text format
                        # Backend API doesn't support function_call_output type
                        call_id = part.get("call_id", "")
                        output = part.get("output", "")
                        content_parts.append({
                            "type": "input_text",
                            "text": f"Tool call {call_id} result:\n{output}"
                        })
                    
                    elif part_type == "tool_result":
                        # Convert tool_result to input_text format
                        tool_use_id = part.get("tool_use_id", "")
                        result_content = part.get("content", "")
                        content_parts.append({
                            "type": "input_text",
                            "text": f"Tool {tool_use_id} result:\n{result_content}"
                        })
                    
                    else:
                        # Unknown type, pass through as-is
                        content_parts.append(part)
            else:
                content_parts = [{"type": "input_text", "text": str(content)}]
            
            codex_input.append({
                "role": role,
                "content": content_parts,
            })
        backend_payload["input"] = codex_input
    
    # Convert tools format if present
    if "tools" in backend_payload and isinstance(backend_payload["tools"], list):
        converted_tools = []
        for tool in backend_payload["tools"]:
            if not isinstance(tool, dict):
                converted_tools.append(tool)
                continue
            
            # OpenAI format: {"type": "function", "function": {"name": "...", ...}}
            # Backend format: {"type": "function", "name": "...", "description": "...", "parameters": {...}}
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                converted_tool = {
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }
                converted_tools.append(converted_tool)
            else:
                # Already in backend format or unknown format, pass through
                converted_tools.append(tool)
        
        backend_payload["tools"] = converted_tools
    
    # Ensure required defaults
    if "store" not in backend_payload:
        backend_payload["store"] = False
    if "instructions" not in backend_payload:
        backend_payload["instructions"] = "You are a helpful assistant."
    if "stream" not in backend_payload:
        backend_payload["stream"] = True
        
    return backend_payload


@app.post("/v1/responses")
async def responses_endpoint(request: Request):
    """Responses API endpoint (OpenAI Responses API compatible)."""
    # Verify API key
    auth = request.headers.get("Authorization", "")
    if not verify_api_key(auth):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Parse request body
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    input_data = body.get("input", [])
    model = body.get("model", "gpt-5.5")
    
    if not input_data:
        raise HTTPException(status_code=400, detail="No input provided")
    
    # Get account
    account = await account_manager.get_account()
    if not account:
        raise HTTPException(status_code=503, detail="No healthy accounts available")
    
    logger.info(f"Responses request: model={model}, input={len(input_data)}, stream={body.get('stream', True)}, account={account.email or account.name}")
    logger.info(f"Request keys: {list(body.keys())}")
    if "tools" in body:
        logger.info(f"Tools: {len(body['tools'])} tools provided")
        if body['tools']:
            first_tool = body['tools'][0]
            if isinstance(first_tool, dict) and 'function' in first_tool:
                logger.info(f"First tool: {first_tool['function'].get('name', 'unknown')}")
    
    # Log input content for debugging (last item detail)
    if input_data and isinstance(input_data, list) and len(input_data) > 0:
        last_item = input_data[-1]
        if isinstance(last_item, dict):
            last_role = last_item.get('role', 'unknown')
            last_content = last_item.get('content', '')
            content_preview = str(last_content)[:200] if not isinstance(last_content, list) else json.dumps(last_content, ensure_ascii=False)[:200]
            logger.info(f"Last input item: role={last_role}, content={content_preview}")
    
    # Build backend payload - pass through ALL fields (tools, reasoning, etc.)
    backend_payload = _convert_input_for_backend(body)
    
    try:
        stream = backend_payload.get("stream", True)
        client_stream = body.get("stream", True)  # Original client request
        
        # Force backend to stream=True regardless of client request
        backend_payload["stream"] = True
        
        if client_stream:
            # Streaming response (pass through SSE directly)
            async def event_generator():
                try:
                    async for chunk in backend.responses_raw(
                        access_token=account.access_token,
                        payload=backend_payload,
                        account_id=account.account_id,
                    ):
                        yield chunk
                    
                    await account_manager.report_success(account)
                    
                except Exception as e:
                    logger.error(f"Stream error: {e}")
                    await account_manager.report_error(account, str(e))
                    raise
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )
        
        else:
            # Non-streaming response (collect all SSE content and build JSON)
            logger.info("Processing non-streaming request")
            
            # Collect all SSE data for debugging
            all_sse_data = []
            full_response = ""
            completed_response = None
            
            async for chunk in backend.responses_raw(
                access_token=account.access_token,
                payload=backend_payload,
                account_id=account.account_id,
            ):
                # Parse SSE events
                lines = chunk.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data_str = line[6:].strip()
                        if data_str and data_str != '[DONE]':
                            all_sse_data.append(data_str)
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
                
                # Build response with usage info if available
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
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Request failed: {e}")
        await account_manager.report_error(account, str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Alias for Codex CLI compatibility (Codex calls /responses, not /v1/responses)
@app.post("/responses")
async def responses_alias(request: Request):
    """Alias endpoint for Codex CLI compatibility."""
    return await responses_endpoint(request)


@app.post("/v1/completions")
async def completions(request: Request):
    """Legacy completions endpoint (redirect to chat)."""
    raise HTTPException(status_code=400, detail="Use /v1/chat/completions instead")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
