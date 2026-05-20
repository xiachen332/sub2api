"""
Sub2API - Modular API Gateway

参考架构：Wei-Shaw/sub2api (Go)
技术栈：Python + FastAPI
"""

import os
import sys
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Use existing chatgpt_backend for now during migration
from chatgpt_backend import ChatGPTBackend as LegacyChatGPTBackend
from account_manager import AccountManager as LegacyAccountManager

# New modular imports
from internal.service.gateway import GatewayService
from internal.service.account import AccountManager
from internal.upstream.chatgpt import ChatGPTBackend
from internal.compat.request import RequestConverter
from internal.compat.response import ResponseConverter
from internal.compat.sse import SSEProcessor
from internal.models.request import ResponsesRequest
from internal.models.response import ResponsesResponse
from pkg.logger import setup_logging

# Setup logging
logger = setup_logging()

# Config
from app.config import HOST, PORT, API_KEY, ACCOUNTS_FILE, AVAILABLE_MODELS

# Global services
legacy_account_manager: Optional[LegacyAccountManager] = None
gateway_service: Optional[GatewayService] = None
legacy_backend: Optional[LegacyChatGPTBackend] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global legacy_account_manager, gateway_service, legacy_backend
    
    logger.info("=" * 50)
    logger.info("Sub2API v2.0 Starting...")
    logger.info("=" * 50)
    
    # Initialize legacy services (during migration)
    legacy_account_manager = LegacyAccountManager(ACCOUNTS_FILE)
    legacy_backend = LegacyChatGPTBackend()
    
    logger.info(f"Loaded {len(legacy_account_manager.accounts)} accounts")
    logger.info(f"API Key: {API_KEY[:10]}...")
    logger.info(f"Server: http://{HOST}:{PORT}")
    logger.info("Ready!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")

app = FastAPI(
    title="Sub2API",
    description="Simplified ChatGPT Backend API Proxy v2.0",
    version="2.0.0",
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

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0", "accounts": len(legacy_account_manager.accounts) if legacy_account_manager else 0}

# Dashboard
@app.get("/")
async def dashboard():
    """Return HTML dashboard."""
    return HTMLResponse(content=dashboard_html())

# API endpoints - use legacy main.py handlers during migration
# This ensures all existing functionality works including cache hits
import importlib.util
spec = importlib.util.spec_from_file_location("legacy_main", "main.py")
legacy_main = importlib.util.module_from_spec(spec)
# Don't execute legacy main to avoid conflicts

# Import legacy handlers directly
from main import (
    responses_endpoint as legacy_responses_endpoint,
    get_response as legacy_get_response,
    delete_response as legacy_delete_response,
)

app.post("/v1/responses")(legacy_responses_endpoint)
app.get("/v1/responses/{response_id}")(legacy_get_response)
app.delete("/v1/responses/{response_id}")(legacy_delete_response)

def verify_api_key(auth_header: str) -> bool:
    """Verify API key from Authorization header."""
    if not auth_header:
        return False
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == API_KEY

def dashboard_html() -> str:
    """Generate dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Sub2API Dashboard</title></head>
    <body>
        <h1>Sub2API Dashboard v2.0</h1>
        <p>Status: Running</p>
        <p>Modular architecture (migration in progress)</p>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
