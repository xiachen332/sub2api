# -*- coding: utf-8 -*-

"""
Account Manager for Sub2API

Loads accounts from JSON, manages pool with round-robin and health checks.
Supports both sub2api format and custom format.
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("sub2api.account")


@dataclass
class Account:
    """Single ChatGPT web account."""
    name: str = ""           # email or identifier
    platform: str = "openai"
    type: str = "oauth"
    access_token: str = ""
    refresh_token: str = ""
    account_id: str = ""
    user_id: str = ""
    email: str = ""
    expires_at: Optional[datetime] = None
    plan_type: str = "free"
    
    # Runtime
    healthy: bool = True
    consecutive_errors: int = 0
    last_error: str = ""
    total_requests: int = 0
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def needs_refresh(self) -> bool:
        if not self.expires_at:
            return False
        time_left = (self.expires_at - datetime.now(timezone.utc)).total_seconds()
        return time_left < 3600  # less than 1 hour
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name or self.email,
            "email": self.email,
            "account_id": self.account_id,
            "healthy": self.healthy,
            "is_expired": self.is_expired,
            "needs_refresh": self.needs_refresh,
            "plan_type": self.plan_type,
            "consecutive_errors": self.consecutive_errors,
            "last_error": self.last_error,
            "total_requests": self.total_requests,
        }


class AccountManager:
    """Manages pool of ChatGPT accounts."""
    
    def __init__(self, accounts_file: str):
        self.accounts_file = Path(accounts_file)
        self.accounts: List[Account] = []
        self._lock = asyncio.Lock()
        self._current_index = 0
        self._load_accounts()
    
    def _load_accounts(self) -> None:
        """Load accounts from JSON file."""
        if not self.accounts_file.exists():
            logger.warning(f"Accounts file not found: {self.accounts_file}")
            return
        
        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON formats
            accounts_data = []
            if isinstance(data, list):
                accounts_data = data
            elif isinstance(data, dict):
                # sub2api format: {"accounts": [...]}
                accounts_data = data.get("accounts", [])
            
            self.accounts = []
            for item in accounts_data:
                account = self._parse_account(item)
                if account:
                    self.accounts.append(account)
            
            logger.info(f"Loaded {len(self.accounts)} accounts from {self.accounts_file}")
            
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
    
    def _parse_account(self, item: Dict[str, Any]) -> Optional[Account]:
        """Parse account from JSON item."""
        try:
            # Extract access token (required)
            access_token = ""
            
            # Format 1: sub2api with nested credentials
            if "credentials" in item and isinstance(item["credentials"], dict):
                creds = item["credentials"]
                access_token = creds.get("access_token", "")
                if not access_token:
                    # Try oauth_token
                    access_token = creds.get("oauth_token", "")
                
                account = Account(
                    name=item.get("name", ""),
                    platform=item.get("platform", "openai"),
                    type=item.get("type", "oauth"),
                    access_token=access_token,
                    account_id=creds.get("chatgpt_account_id", ""),
                    user_id=creds.get("chatgpt_user_id", ""),
                    email=creds.get("email", item.get("name", "")),
                    plan_type=creds.get("plan_type", "free"),
                )
                
                # Parse expiration
                expires_str = creds.get("expires_at", "")
                if expires_str:
                    try:
                        account.expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                return account
            
            # Format 2: flat format
            elif "access_token" in item:
                account = Account(
                    name=item.get("name", item.get("email", "")),
                    platform=item.get("platform", "openai"),
                    type=item.get("type", "oauth"),
                    access_token=item.get("access_token", ""),
                    refresh_token=item.get("refresh_token", ""),
                    account_id=item.get("account_id", ""),
                    user_id=item.get("user_id", ""),
                    email=item.get("email", item.get("name", "")),
                    plan_type=item.get("plan_type", "free"),
                )
                
                expires_str = item.get("expires_at", item.get("expired", ""))
                if expires_str:
                    try:
                        account.expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                return account
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse account: {e}")
            return None
    
    async def get_account(self) -> Optional[Account]:
        """Get next healthy account (round-robin)."""
        async with self._lock:
            if not self.accounts:
                return None
            
            attempts = 0
            while attempts < len(self.accounts):
                account = self.accounts[self._current_index]
                self._current_index = (self._current_index + 1) % len(self.accounts)
                
                if account.healthy and not account.is_expired:
                    account.total_requests += 1
                    return account
                
                attempts += 1
            
            logger.warning("No healthy accounts available")
            return None
    
    async def report_error(self, account: Account, error: str) -> None:
        """Report error for an account."""
        async with self._lock:
            account.last_error = error
            account.consecutive_errors += 1
            
            if account.consecutive_errors >= 3:
                account.healthy = False
                logger.warning(f"Account marked unhealthy: {account.email or account.name}")
    
    async def report_success(self, account: Account) -> None:
        """Report successful request."""
        async with self._lock:
            account.consecutive_errors = 0
            account.last_error = ""
            if not account.healthy:
                account.healthy = True
                logger.info(f"Account recovered: {account.email or account.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get account pool statistics."""
        total = len(self.accounts)
        healthy = sum(1 for a in self.accounts if a.healthy and not a.is_expired)
        expired = sum(1 for a in self.accounts if a.is_expired)
        
        return {
            "total": total,
            "healthy": healthy,
            "expired": expired,
            "unhealthy": total - healthy - expired,
            "accounts": [a.to_dict() for a in self.accounts],
        }
    
    def get_healthy_count(self) -> int:
        """Count healthy accounts."""
        return sum(1 for a in self.accounts if a.healthy and not a.is_expired)
