"""
Authentication Service

参考：Wei-Shaw/sub2api backend/internal/service/auth.go
支持多种认证方式：OAuth、API Key、Service Account
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("sub2api.auth")

class AuthType(Enum):
    """Authentication types."""
    OAUTH = "oauth"
    API_KEY = "apikey"
    SERVICE_ACCOUNT = "service_account"

@dataclass
class AuthCredentials:
    """Authentication credentials."""
    auth_type: AuthType
    access_token: str = ""
    refresh_token: str = ""
    expires_at: Optional[int] = None
    api_key: str = ""
    base_url: str = ""
    
    def is_expired(self) -> bool:
        """Check if credentials are expired."""
        if self.expires_at is None:
            return False
        from time import time
        return time() > self.expires_at
    
    def get_auth_header(self) -> str:
        """Get Authorization header value."""
        if self.auth_type == AuthType.API_KEY:
            return f"Bearer {self.api_key}"
        elif self.auth_type == AuthType.OAUTH:
            return f"Bearer {self.access_token}"
        return ""

class AuthService:
    """Authentication service for managing different auth methods."""
    
    def __init__(self):
        self.credentials: Dict[str, AuthCredentials] = {}
    
    def add_credentials(self, account_id: str, credentials: AuthCredentials):
        """Add credentials for an account."""
        self.credentials[account_id] = credentials
        logger.info(f"Added {credentials.auth_type.value} credentials for {account_id}")
    
    def get_credentials(self, account_id: str) -> Optional[AuthCredentials]:
        """Get credentials for an account."""
        return self.credentials.get(account_id)
    
    def validate_credentials(self, account_id: str) -> bool:
        """Validate credentials for an account."""
        creds = self.get_credentials(account_id)
        if not creds:
            return False
        if creds.is_expired():
            logger.warning(f"Credentials expired for {account_id}")
            return False
        return True
    
    async def refresh_oauth_token(self, account_id: str) -> bool:
        """Refresh OAuth token for an account."""
        creds = self.get_credentials(account_id)
        if not creds or creds.auth_type != AuthType.OAUTH:
            return False
        
        logger.info(f"Refreshing OAuth token for {account_id}")
        # TODO: Implement actual OAuth refresh flow
        return True

# Global auth service instance
auth_service = AuthService()
