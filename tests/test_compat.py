"""
Basic tests for Sub2API

Run with: pytest tests/
"""

import json
import pytest
from internal.compat.request import RequestConverter
from internal.compat.response import ResponseConverter
from internal.compat.sse import SSEProcessor

class TestRequestConverter:
    """Test request conversion."""
    
    def test_convert_tools(self):
        """Test tool format conversion."""
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "parameters": {"type": "object", "properties": {}},
                }
            }
        ]
        
        result = RequestConverter.convert_tools(openai_tools)
        
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "get_weather"
        assert "function" not in result[0]  # Nested object removed
    
    def test_convert_input_text(self):
        """Test text input conversion."""
        input_data = [
            {"role": "user", "content": "Hello"},
        ]
        
        result = RequestConverter.convert_input(input_data)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["content"]) == 1
        assert result[0]["content"][0]["type"] == "input_text"
    
    def test_convert_function_call_output(self):
        """Test function_call_output conversion."""
        input_data = [
            {"type": "function_call_output", "call_id": "call_123", "output": "25°C"},
        ]
        
        result = RequestConverter.convert_input(input_data)
        
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert "Tool call call_123 result" in result[0]["content"][0]["text"]
    
    def test_convert_request(self):
        """Test full request conversion."""
        body = {
            "model": "gpt-5.5",
            "input": [
                {"role": "user", "content": "Hello"},
            ],
            "tools": [
                {"type": "function", "function": {"name": "test"}},
            ],
        }
        
        result = RequestConverter.convert_request(body)
        
        assert result["store"] == False
        assert result["instructions"] == "You are a helpful assistant."
        assert result["stream"] == True

class TestSSEProcessor:
    """Test SSE processing."""
    
    def test_parse_sse_chunk(self):
        """Test SSE chunk parsing."""
        chunk = "event: text\ndata: {\"text\": \"Hello\"}\n\n"
        
        events = SSEProcessor.parse_sse_chunk(chunk)
        
        assert len(events) == 1
        assert events[0]["event_type"] == "text"
        assert events[0]["data"]["text"] == "Hello"
    
    def test_extract_content(self):
        """Test content extraction."""
        events = [
            {"event_type": "response.output_text.delta", "data": {"delta": "Hello"}},
            {"event_type": "response.output_text.delta", "data": {"delta": " World"}},
        ]
        
        content = SSEProcessor.extract_content_from_events(events)
        
        assert content == "Hello World"
    
    def test_build_sse_event(self):
        """Test SSE event building."""
        event = SSEProcessor.build_sse_event("test", {"key": "value"})
        
        assert "event: test" in event
        assert "data: {\"key\": \"value\"}" in event

class TestErrorHandling:
    """Test error handling."""
    
    def test_sanitize_error_message(self):
        """Test error message sanitization."""
        from internal.service.errors import sanitize_error_message
        
        message = "Error with token: Bearer eyJ0eXAiOiJKV1QiLCJhbGci"
        result = sanitize_error_message(message)
        
        assert "Bearer [REDACTED]" in result
        assert "eyJ0eXAi" not in result
    
    def test_classify_error(self):
        """Test error classification."""
        from internal.service.errors import classify_upstream_error, ErrorType
        
        assert classify_upstream_error(401, "auth failed") == ErrorType.AUTH_ERROR
        assert classify_upstream_error(429, "rate limited") == ErrorType.RATE_LIMIT
        assert classify_upstream_error(500, "server error") == ErrorType.UPSTREAM_ERROR

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
