# test_rag.py
from database import SessionLocal
from models import Tenant
from rag import Retriever, build_prompt

def test_rag():
    print("🧪 Testing RAG Pipeline")
    print("=" * 40)
    
    db = SessionLocal()
    tenant = db.query(Tenant).first()
    
    if not tenant:
        print("❌ No tenant found.")
        db.close()
        return
    
    print(f"✅ Using tenant: {tenant.name} (ID: {tenant.id})")
    
    # Initialize retriever
    retriever = Retriever()
    
    # Test queries
    queries = [
        "What are your hours?",
        "Do you accept insurance?",
        "Where are you located?"
    ]
    
    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        
        # Retrieve relevant chunks
        chunks = retriever.retrieve(tenant.id, query, top_k=3)
        
        print(f"   Found {len(chunks)} chunks")
        for i, chunk in enumerate(chunks, 1):
            print(f"   {i}. Score: {chunk['score']:.3f} - {chunk['text'][:60]}...")
        
        # Build prompt
        prompt = build_prompt(query, chunks, tenant.name)
        print(f"   📝 Prompt length: {len(prompt)} characters")
    
    db.close()
    print("\n" + "=" * 40)
    print("✅ RAG test completed!")

if __name__ == "__main__":
    test_rag()