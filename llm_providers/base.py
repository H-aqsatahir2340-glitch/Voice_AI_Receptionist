# llm_providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMProvider(ABC):
    """Base class for all LLM providers"""
    
    @abstractmethod
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Any:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dicts [{"role": "user", "content": "..."}]
            tools: Optional list of tool definitions
            **kwargs: Additional provider-specific parameters
        
        Returns:
            The LLM response (provider-specific format)
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model name"""
        pass
    
    @abstractmethod
    def extract_content(self, response: Any) -> str:
        """Extract text content from the response"""
        pass
    
    @abstractmethod
    def extract_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from the response"""
        pass