"""
Account Management Service

参考：Wei-Shaw/sub2api backend/internal/service/account.go
"""

import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger("sub2api.account")

@dataclass
class Account:
    """Represents a ChatGPT account."""
    account_id: str
    email: str
    password: str
    access_token: str = ""
    refresh_token: str = ""
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    is_active: bool = True
    last_used: Optional[datetime] = None
    error_count: int = 0
    total_requests: int = 0
    platform: str = "openai"  # openai, anthropic, gemini
    account_type: str = "oauth"  # oauth, apikey, service_account
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    def is_healthy(self) -> bool:
        return self.is_active and self.error_count < 5
    
    def record_error(self, error: str):
        self.error_count += 1
        logger.warning(f"Account {self.email} error #{self.error_count}: {error}")
        if self.error_count >= 5:
            self.is_active = False
            logger.error(f"Account {self.email} deactivated after 5 errors")
    
    def record_success(self):
        self.error_count = max(0, self.error_count - 1)
        self.total_requests += 1
        self.last_used = datetime.now()

class AccountManager:
    """Manages a pool of ChatGPT accounts."""
    
    def __init__(self, accounts_file: str):
        self.accounts_file = accounts_file
        self.accounts: List[Account] = []
        self._load_accounts()
        self._current_index = 0
    
    def _load_accounts(self):
        """Load accounts from JSON file."""
        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.accounts = []
            for acc in data:
                account = Account(
                    account_id=acc.get("id", ""),
                    email=acc.get("email", ""),
                    password=acc.get("password", ""),
                    access_token=acc.get("access_token", ""),
                    refresh_token=acc.get("refresh_token", ""),
                    platform=acc.get("platform", "openai"),
                    account_type=acc.get("type", "oauth"),
                )
                if acc.get("expires_at"):
                    account.expires_at = datetime.fromisoformat(acc["expires_at"])
                self.accounts.append(account)
            
            healthy = sum(1 for a in self.accounts if a.is_healthy())
            logger.info(f"Loaded {len(self.accounts)} accounts, {healthy} healthy")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
            self.accounts = []
    
    def get_account(self) -> Optional[Account]:
        """Get next available account using round-robin."""
        if not self.accounts:
            return None
        
        # Find next healthy account
        for _ in range(len(self.accounts)):
            idx = self._current_index % len(self.accounts)
            self._current_index += 1
            account = self.accounts[idx]
            if account.is_healthy():
                return account
        
        logger.error("No healthy accounts available")
        return None
    
    def get_account_by_id(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        for account in self.accounts:
            if account.account_id == account_id:
                return account
        return None
    
    def report_error(self, account: Account, error: str):
        """Report an error for an account."""
        account.record_error(error)
        self._save_accounts()
    
    def report_success(self, account: Account):
        """Report a successful request."""
        account.record_success()
        self._save_accounts()
    
    def _save_accounts(self):
        """Save accounts back to file."""
        try:
            data = []
            for acc in self.accounts:
                data.append({
                    "id": acc.account_id,
                    "email": acc.email,
                    "password": acc.password,
                    "access_token": acc.access_token,
                    "refresh_token": acc.refresh_token,
                    "expires_at": acc.expires_at.isoformat(),
                    "platform": acc.platform,
                    "type": acc.account_type,
                })
            with open(self.accounts_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get account statistics."""
        total = len(self.accounts)
        healthy = sum(1 for a in self.accounts if a.is_healthy())
        active = sum(1 for a in self.accounts if a.is_active)
        total_requests = sum(a.total_requests for a in self.accounts)
        
        return {
            "total": total,
            "healthy": healthy,
            "active": active,
            "total_requests": total_requests,
            "accounts": [
                {
                    "id": a.account_id,
                    "email": a.email,
                    "healthy": a.is_healthy(),
                    "active": a.is_active,
                    "requests": a.total_requests,
                    "last_used": a.last_used.isoformat() if a.last_used else None,
                }
                for a in self.accounts
            ]
        }
