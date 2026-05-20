"""
Request Models

参考：Wei-Shaw/sub2api backend/internal/pkg/apicompat/types.go
OpenAI Responses API request types
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ResponsesContentPart:
    """A content part in a message."""
    type: str = ""
    text: str = ""
    image_url: str = ""
    detail: str = "auto"

@dataclass
class ResponsesInputItem:
    """An input item in the conversation."""
    role: str = ""
    content: str = ""
    type: str = ""
    call_id: str = ""
    name: str = ""
    arguments: str = ""
    output: str = ""

@dataclass
class ResponsesTool:
    """A tool definition."""
    type: str = ""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = None

@dataclass
class ResponsesRequest:
    """OpenAI Responses API request."""
    model: str = ""
    input: List[Dict[str, Any]] = None
    stream: bool = True
    tools: List[Dict[str, Any]] = None
    instructions: str = ""
    store: bool = False
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    reasoning: Optional[Dict[str, Any]] = None
    tool_choice: Optional[Dict[str, Any]] = None
    parallel_tool_calls: bool = True
    prompt_cache_key: Optional[str] = None
    text: Optional[Dict[str, Any]] = None
    client_metadata: Optional[Dict[str, Any]] = None
    include: Optional[List[str]] = None
