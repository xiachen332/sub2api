# -*- coding: utf-8 -*-

"""
Simplified Sub2API - ChatGPT Backend API Proxy

Provides OpenAI-compatible API using ChatGPT web accounts.
"""

import os
from pathlib import Path

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "16731"))
API_KEY = os.getenv("API_KEY", "maple3474468992")

# Accounts
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "accounts.json")

# ChatGPT Backend API
CHATGPT_BACKEND_BASE = "https://chatgpt.com/backend-api"

# Model mapping (alias -> real model name)
MODEL_ALIASES = {
    "gpt-5.4": "gpt-4o",
    "gpt-5.4-mini": "gpt-4o-mini",
    "gpt-5.3-codex": "gpt-4o",
    "gpt-5.2": "gpt-4o",
    "gpt-5.1-codex": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4": "gpt-4",
    "gpt-4-turbo": "gpt-4-turbo",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "claude-sonnet-4": "claude-sonnet-4",
    "claude-opus-4": "claude-opus-4",
    "claude-haiku-4": "claude-haiku-4",
}

# Available models for /v1/models
AVAILABLE_MODELS = [
    # GPT 5.x 系列
    {"id": "gpt-5.1-codex", "object": "model", "owned_by": "openai"},
    {"id": "gpt-5.2", "object": "model", "owned_by": "openai"},
    {"id": "gpt-5.3-codex", "object": "model", "owned_by": "openai"},
    {"id": "gpt-5.4", "object": "model", "owned_by": "openai"},
    {"id": "gpt-5.4-mini", "object": "model", "owned_by": "openai"},
    {"id": "gpt-5.5", "object": "model", "owned_by": "openai"},
    # OpenAI o 系列
    {"id": "o1", "object": "model", "owned_by": "openai"},
    {"id": "o1-mini", "object": "model", "owned_by": "openai"},
    {"id": "o3", "object": "model", "owned_by": "openai"},
    {"id": "o3-mini", "object": "model", "owned_by": "openai"},
    # Anthropic Claude 系列
    {"id": "claude-sonnet-4", "object": "model", "owned_by": "anthropic"},
    {"id": "claude-opus-4", "object": "model", "owned_by": "anthropic"},
    {"id": "claude-haiku-4", "object": "model", "owned_by": "anthropic"},
]
