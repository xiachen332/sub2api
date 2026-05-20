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
account_manager: Optional[AccountManager] = None
gateway_service: Optional[GatewayService] = None
backend: Optional[ChatGPTBackend] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global account_manager, gateway_service, backend
    
    logger.info("=" * 50)
    logger.info("Sub2API Starting...")
    logger.info("=" * 50)
    
    # Initialize services
    account_manager = AccountManager(ACCOUNTS_FILE)
    backend = ChatGPTBackend()
    gateway_service = GatewayService(
        account_manager=account_manager,
        backend=backend,
        config={"store": False}
    )
    
    # Store in app state for access from routers
    app.state.account_manager = account_manager
    app.state.gateway_service = gateway_service
    app.state.backend = backend
    
    logger.info(f"Loaded {len(account_manager.accounts)} accounts")
    logger.info(f"API Key: {API_KEY[:10]}...")
    logger.info(f"Server: http://{HOST}:{PORT}")
    logger.info("Ready!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")

app = FastAPI(
    title="Sub2API",
    description="Simplified ChatGPT Backend API Proxy",
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
    return {"status": "ok", "version": "2.0.0"}

# Dashboard
@app.get("/")
async def dashboard():
    """Return HTML dashboard."""
    return HTMLResponse(content=dashboard_html())

# API endpoints
from app.routers import responses
app.include_router(responses.router, prefix="/v1")

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
    # Simple HTML dashboard
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Sub2API Dashboard</title></head>
    <body>
        <h1>Sub2API Dashboard</h1>
        <p>Version: 2.0.0</p>
        <p>Status: Running</p>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
