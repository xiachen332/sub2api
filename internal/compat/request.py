"""
Request Compatibility Layer

参考：Wei-Shaw/sub2api backend/internal/pkg/apicompat/
负责 OpenAI Responses API 和后端 API 之间的格式转换
"""

import json
from typing import Dict, Any, List, Optional

class RequestConverter:
    """Converts between OpenAI Responses API and backend API formats."""
    
    @staticmethod
    def convert_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI tool format to backend format.
        
        OpenAI format: {"type": "function", "function": {"name": "...", ...}}
        Backend format: {"type": "function", "name": "...", "description": "...", "parameters": {...}}
        """
        converted = []
        for tool in tools:
            if not isinstance(tool, dict):
                converted.append(tool)
                continue
            
            # OpenAI format with nested function object
            if tool.get("type") == "function" and "function" in tool:
                func = tool["function"]
                converted.append({
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
            else:
                # Already in backend format or unknown
                converted.append(tool)
        
        return converted
    
    @staticmethod
    def convert_input(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert OpenAI input format to backend input format.
        
        Handles:
        - text → input_text
        - image_url → input_image
        - function_call_output → input_text (with tool result)
        - tool_result → input_text
        """
        codex_input = []
        
        for item in input_data:
            if not isinstance(item, dict):
                codex_input.append(item)
                continue
            
            # Handle special item types (function_call_output without role/content)
            item_type = item.get("type", "")
            
            if item_type == "function_call_output":
                # Convert to system message with input_text
                call_id = item.get("call_id", "")
                output = item.get("output", "")
                codex_input.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Tool call {call_id} result:\n{output}"}]
                })
                continue
            
            elif item_type == "tool_result":
                # Convert to system message with input_text
                tool_use_id = item.get("tool_use_id", "")
                result_content = item.get("content", "")
                codex_input.append({
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Tool {tool_use_id} result:\n{result_content}"}]
                })
                continue
            
            # Normal message item with role and content
            role = item.get("role", "user")
            content = item.get("content", "")
            
            if isinstance(content, str):
                content_parts = [{"type": "input_text", "text": content}]
            elif isinstance(content, list):
                content_parts = RequestConverter._convert_content_parts(content)
            else:
                content_parts = [{"type": "input_text", "text": str(content)}]
            
            codex_input.append({
                "role": role,
                "content": content_parts,
            })
        
        return codex_input
    
    @staticmethod
    def _convert_content_parts(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert content parts to backend format."""
        content_parts = []
        
        for part in parts:
            if not isinstance(part, dict):
                content_parts.append(part)
                continue
            
            part_type = part.get("type", "")
            
            if part_type == "text":
                content_parts.append({"type": "input_text", "text": part.get("text", "")})
            
            elif part_type == "image_url":
                # Convert OpenAI image_url format to backend input_image format
                image_url = part.get("image_url", {})
                if isinstance(image_url, dict):
                    url = image_url.get("url", "")
                    detail = image_url.get("detail", "auto")
                else:
                    url = image_url
                    detail = "auto"
                
                content_parts.append({
                    "type": "input_image",
                    "image_url": url,
                    "detail": detail,
                })
            
            elif part_type == "input_image":
                # Already in backend format
                content_parts.append(part)
            
            elif part_type == "function_call_output":
                # Convert function_call_output to input_text
                call_id = part.get("call_id", "")
                output = part.get("output", "")
                content_parts.append({
                    "type": "input_text",
                    "text": f"Tool call {call_id} result:\n{output}"
                })
            
            elif part_type == "tool_result":
                # Convert tool_result to input_text
                tool_use_id = part.get("tool_use_id", "")
                result_content = part.get("content", "")
                content_parts.append({
                    "type": "input_text",
                    "text": f"Tool {tool_use_id} result:\n{result_content}"
                })
            
            else:
                # Unknown type, pass through as-is
                content_parts.append(part)
        
        return content_parts
    
    @staticmethod
    def convert_request(body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert OpenAI Responses API request to backend format.
        
        Handles:
        - input format conversion
        - tools format conversion
        - default values
        """
        backend_payload = dict(body)
        
        # Convert input
        if "input" in backend_payload:
            backend_payload["input"] = RequestConverter.convert_input(backend_payload["input"])
        
        # Convert tools
        if "tools" in backend_payload and isinstance(backend_payload["tools"], list):
            backend_payload["tools"] = RequestConverter.convert_tools(backend_payload["tools"])
        
        # Ensure required defaults
        if "store" not in backend_payload:
            backend_payload["store"] = False
        if "instructions" not in backend_payload:
            backend_payload["instructions"] = "You are a helpful assistant."
        
        # Force backend streaming (backend requires stream=True)
        backend_payload["stream"] = True
        
        return backend_payload
