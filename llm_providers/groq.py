# llm_providers/groq.py
from openai import OpenAI
from config import Config
from .base import LLMProvider
import json
from typing import List, Dict, Any, Optional

class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "openai/gpt-oss-120b"
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        """Generate a response from Groq"""
        
        # Prepare parameters
        params = {
            "model": self.model,
            "messages": messages,
            **kwargs
        }
        
        # Only add tool_choice if tools are provided
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**params)
        return response.choices[0].message
    
    def get_model_name(self) -> str:
        return self.model
    
    def extract_content(self, response: Any) -> str:
        """Extract text content from the response"""
        if hasattr(response, 'content') and response.content:
            return response.content
        return str(response)
    
    def extract_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from the response"""
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = []
            for tc in response.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                })
            return tool_calls
        return None