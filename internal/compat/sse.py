"""
SSE (Server-Sent Events) Processor

参考：Wei-Shaw/sub2api backend/internal/pkg/apicompat/
负责处理 SSE 流式响应的解析和转换
"""

import json
from typing import Dict, Any, List, Optional, AsyncGenerator

class SSEProcessor:
    """Processes SSE (Server-Sent Events) streams."""
    
    @staticmethod
    def parse_sse_chunk(chunk: str) -> List[Dict[str, Any]]:
        """
        Parse an SSE chunk into individual events.
        
        SSE format:
        event: xxx\n
        data: xxx\n\n
        """
        events = []
        buffer = ""
        
        for line in chunk.strip().split('\n'):
            if line == "":
                # Empty line means end of event
                if buffer:
                    events.append(buffer)
                    buffer = ""
            else:
                buffer += line + "\n"
        
        # Handle remaining buffer
        if buffer.strip():
            events.append(buffer)
        
        return [SSEProcessor._parse_event(e) for e in events if e.strip()]
    
    @staticmethod
    def _parse_event(event_str: str) -> Optional[Dict[str, Any]]:
        """Parse a single SSE event string."""
        event_type = ""
        data = ""
        
        for line in event_str.strip().split('\n'):
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:].strip()
        
        if not data:
            return None
        
        try:
            parsed = json.loads(data)
            return {
                "event_type": event_type,
                "data": parsed,
            }
        except json.JSONDecodeError:
            return {
                "event_type": event_type,
                "raw_data": data,
            }
    
    @staticmethod
    def extract_content_from_events(events: List[Dict[str, Any]]) -> str:
        """Extract text content from a list of SSE events."""
        content = ""
        for event in events:
            if not event:
                continue
            data = event.get("data", {})
            event_type = event.get("event_type", "")
            
            if event_type == "response.output_text.delta":
                content += data.get("delta", "")
            elif event_type == "text":
                content += data.get("text", "")
        
        return content
    
    @staticmethod
    def extract_completed_response(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Extract the completed response from events."""
        for event in events:
            if not event:
                continue
            data = event.get("data", {})
            event_type = event.get("event_type", "")
            
            if event_type == "response.completed" and "response" in data:
                return data["response"]
        
        return None
    
    @staticmethod
    def build_sse_event(event_type: str, data: Dict[str, Any]) -> str:
        """Build an SSE event string."""
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
