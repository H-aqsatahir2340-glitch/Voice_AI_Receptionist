# llm_providers/factory.py
from .base import LLMProvider
from .groq import GroqProvider

# Available providers
PROVIDERS = {
    "groq": GroqProvider,
    # Add more providers here as needed:
    # "openai": OpenAIProvider,
    # "claude": ClaudeProvider,
}

def get_llm_provider(provider_name: str = "groq") -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.
    
    Args:
        provider_name: Name of the provider ('groq', 'openai', 'claude')
    
    Returns:
        An instance of the requested LLM provider
    """
    provider_class = PROVIDERS.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")
    
    return provider_class()