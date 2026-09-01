# test_llm.py
from database import SessionLocal
from models import Tenant
from llm_client import LLMClient
from llm_providers import get_llm_provider

def test_llm_provider():
    """Test the LLM provider directly (without tenant)"""
    print("🔧 Testing LLM Provider")
    print("=" * 40)
    
    try:
        # Get provider
        provider = get_llm_provider("groq")
        print(f"✅ Provider: {provider.get_model_name()}")
        
        # Test simple message
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! What are your hours?"}
        ]
        
        response = provider.generate_response(messages)
        content = provider.extract_content(response)
        print(f"📝 Response: {content}")
        print("✅ Provider test passed!\n")
    except Exception as e:
        print(f"❌ Provider test failed: {e}\n")


def test_tenant_llm():
    """Test the tenant-aware LLM client"""
    print("🔧 Testing Tenant-Aware LLM Client")
    print("=" * 40)
    
    db = SessionLocal()
    
    try:
        # Get a tenant
        tenant = db.query(Tenant).first()
        
        if not tenant:
            print("❌ No tenant found. Run test_db_tools.py first to create one.")
            return
        
        print(f"✅ Using tenant: {tenant.name} (ID: {tenant.id})")
        
        # Create LLM client
        llm_client = LLMClient(tenant.id, db)
        print(f"✅ LLM Client initialized with provider: {llm_client.provider.get_model_name()}")
        
        # Test conversation
        messages = []
        test_queries = [
            "What are your hours?",
            "Book me for tomorrow at 11 AM",
            "Where are you located?"
        ]
        
        for query in test_queries:
            print(f"\n👤 User: {query}")
            
            try:
                response, tool_calls = llm_client.generate_response(query, messages)
                
                print(f"🤖 AI: {response}")
                if tool_calls:
                    print(f"🔧 Tool calls: {tool_calls}")
                
                # Add to conversation history
                messages.append({"role": "user", "content": query})
                messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                print(f"❌ Error generating response: {e}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        db.close()
    
    print("\n" + "=" * 40)
    print("✅ All tests completed!")


if __name__ == "__main__":
    test_llm_provider()
    test_tenant_llm()