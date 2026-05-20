"""__init__.py for internal package"""

from .compat.request import RequestConverter
from .compat.response import ResponseConverter
from .compat.sse import SSEProcessor
from .service.account import AccountManager, Account
from .service.auth import AuthService, AuthCredentials, AuthType
from .service.errors import UpstreamError, FailoverError, ErrorType
from .service.gateway import GatewayService
from .upstream.chatgpt import ChatGPTBackend
from .models.request import ResponsesRequest
from .models.response import ResponsesResponse

__all__ = [
    "RequestConverter", "ResponseConverter", "SSEProcessor",
    "AccountManager", "Account",
    "AuthService", "AuthCredentials", "AuthType",
    "UpstreamError", "FailoverError", "ErrorType",
    "GatewayService",
    "ChatGPTBackend",
    "ResponsesRequest", "ResponsesResponse",
]
