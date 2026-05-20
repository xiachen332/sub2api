"""
Error handling and failover utilities

参考：Wei-Shaw/sub2api backend/internal/service/errors.go
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("sub2api.errors")

class ErrorType(Enum):
    """Error types for upstream errors."""
    UPSTREAM_ERROR = "upstream_error"
    AUTH_ERROR = "auth_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    INVALID_REQUEST = "invalid_request"
    FAILOVER = "failover"

class UpstreamError(Exception):
    """Upstream API error."""
    
    def __init__(
        self,
        error_type: ErrorType,
        status_code: int,
        message: str,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error": {
                "type": self.error_type.value,
                "message": self.message,
                "status_code": self.status_code,
                "retryable": self.retryable,
                "details": self.details,
            }
        }

class FailoverError(UpstreamError):
    """Error that triggers failover to another account."""
    
    def __init__(self, status_code: int, message: str, response_body: str = ""):
        super().__init__(
            error_type=ErrorType.FAILOVER,
            status_code=status_code,
            message=message,
            retryable=True,
        )
        self.response_body = response_body

def sanitize_error_message(message: str) -> str:
    """Sanitize error message to remove sensitive information."""
    # Remove tokens, keys, passwords
    import re
    
    # Remove bearer tokens
    message = re.sub(r'Bearer\s+\S+', 'Bearer [REDACTED]', message)
    
    # Remove API keys (hex strings longer than 20 chars)
    message = re.sub(r'[a-f0-9]{32,}', '[REDACTED]', message)
    
    # Remove email addresses
    message = re.sub(r'\S+@\S+\.[a-zA-Z]{2,}', '[EMAIL]', message)
    
    return message

def classify_upstream_error(status_code: int, message: str) -> ErrorType:
    """Classify upstream error by status code and message."""
    if status_code == 401 or status_code == 403:
        return ErrorType.AUTH_ERROR
    elif status_code == 429:
        return ErrorType.RATE_LIMIT
    elif status_code == 408:
        return ErrorType.TIMEOUT
    elif status_code >= 500:
        return ErrorType.UPSTREAM_ERROR
    elif status_code == 400:
        return ErrorType.INVALID_REQUEST
    else:
        return ErrorType.UPSTREAM_ERROR

def is_retryable(status_code: int, error_type: ErrorType) -> bool:
    """Determine if an error is retryable."""
    if error_type == ErrorType.RATE_LIMIT:
        return True
    if error_type == ErrorType.TIMEOUT:
        return True
    if status_code >= 500:
        return True
    if status_code == 408:
        return True
    return False
