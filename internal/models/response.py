"""
Response Models

参考：Wei-Shaw/sub2api backend/internal/pkg/apicompat/types.go
OpenAI Responses API response types
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ResponsesContentBlock:
    """A content block in a response message."""
    type: str = ""
    text: str = ""
    thinking: str = ""

@dataclass
class ResponsesOutputItem:
    """An output item in the response."""
    type: str = ""
    id: str = ""
    role: str = ""
    content: List[Dict[str, Any]] = None
    name: str = ""
    arguments: str = ""
    call_id: str = ""
    status: str = ""

@dataclass
class ResponsesUsage:
    """Usage statistics for a response."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_tokens_details: Dict[str, int] = None
    output_tokens_details: Dict[str, int] = None

@dataclass
class ResponsesResponse:
    """OpenAI Responses API response."""
    id: str = ""
    object: str = "response"
    created_at: int = 0
    model: str = ""
    output: List[Dict[str, Any]] = None
    status: str = "completed"
    usage: Optional[ResponsesUsage] = None
    incomplete_details: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
