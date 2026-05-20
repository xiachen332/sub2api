"""
Configuration module
"""

import os

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "16731"))
API_KEY = os.getenv("API_KEY", "maple3474468992")
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "accounts.json")
AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "o1",
    "o1-mini",
    "o3-mini",
    "gpt-5.4",
    "gpt-5.5",
]
