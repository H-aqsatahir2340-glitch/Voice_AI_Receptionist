# llm_client.py
from sqlalchemy.orm import Session
from llm_providers import get_llm_provider
from models import Tenant
from config import Config

class LLMClient:
    """
    Tenant-aware LLM client.
    Uses the configured provider with tenant-specific context.
    """
    
    def __init__(self, tenant_id: int, db: Session):
        """
        Initialize the LLM client for a specific tenant.
        
        Args:
            tenant_id: The tenant's ID
            db: Database session
        """
        self.tenant_id = tenant_id
        self.db = db
        
        # Get the LLM provider
        provider_name = getattr(Config, 'LLM_PROVIDER', 'groq')
        self.provider = get_llm_provider(provider_name)
        
        # Get tenant data
        self.tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        
        # Build system prompt from tenant config
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt based on tenant configuration."""
        if not self.tenant:
            return "You are a helpful AI assistant."
        
        config = self.tenant.config or {}
        
        business_name = self.tenant.name
        hours = config.get('hours', '9 AM to 6 PM, Monday to Friday')
        services = config.get('services', 'General services')
        
        return f"""You are a friendly, efficient AI receptionist for {business_name}.

Business hours: {hours}
Services offered: {services}

Your job:
- Help callers check availability, book appointments
- Answer questions about hours, location, services
- Take messages when needed

Keep responses short and natural — this will be spoken aloud over the phone.
"""
    
    def generate_response(
        self,
        user_message: str,
        conversation_history: list = None,
        tools: list = None
    ) -> tuple:
        """
        Generate a response using the tenant's LLM.
        
        Args:
            user_message: The user's message
            conversation_history: Previous messages [{"role": "user", "content": "..."}]
            tools: Optional tool definitions
        
        Returns:
            (response_text, tool_calls)
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({"role": "user", "content": user_message})
        
        # Generate response
        response = self.provider.generate_response(messages, tools=tools)
        
        # Extract content
        content = self.provider.extract_content(response)
        
        # Extract tool calls
        tool_calls = self.provider.extract_tool_calls(response)
        
        return content, tool_calls