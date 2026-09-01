# test_rag_llm.py
from database import SessionLocal
from models import Tenant
from rag.pipeline import rag_answer

def test_rag_llm():
    print("🧪 Testing RAG + LLM Pipeline")
    print("=" * 40)
    
    db = SessionLocal()
    tenant = db.query(Tenant).first()
    db.close()
    
    if not tenant:
        print("❌ No tenant found.")
        return
    
    print(f"✅ Using tenant: {tenant.name} (ID: {tenant.id})")
    
    queries = [
        "What are your hours?",
        "Do you accept insurance?",
        "Where are you located?"
    ]
    
    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        
        answer, chunks = rag_answer(tenant.id, query)
        
        print(f"📝 Answer: {answer}")
        print(f"📄 Used {len(chunks)} chunks")
        for i, chunk in enumerate(chunks[:2], 1):
            print(f"   {i}. {chunk['text'][:60]}...")

if __name__ == "__main__":
    test_rag_llm()