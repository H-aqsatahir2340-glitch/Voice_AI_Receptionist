# test_ingestion.py
from database import SessionLocal
from models import Tenant
from qdrant_utils import get_qdrant_client, create_collection_if_not_exists
from ingestion import chunk_text, store_chunks_in_qdrant, search_similar_chunks

def test_ingestion():
    print("🧪 Testing Ingestion Pipeline")
    print("=" * 40)
    
    # ──────────────────────────────────────────────
    # 1. Get Qdrant client and create collection
    # ──────────────────────────────────────────────
    client = get_qdrant_client()
    create_collection_if_not_exists("knowledge")
    
    # ──────────────────────────────────────────────
    # 2. Get a tenant from the database
    # ──────────────────────────────────────────────
    db = SessionLocal()
    tenant = db.query(Tenant).first()
    
    if not tenant:
        print("❌ No tenant found. Run test_db_tools.py first to create one.")
        db.close()
        return
    
    print(f"✅ Using tenant: {tenant.name} (ID: {tenant.id})")
    
    # ──────────────────────────────────────────────
    # 3. Create test documents
    # ──────────────────────────────────────────────
    test_docs = [
        "We're open Monday to Friday from 9 AM to 6 PM.",
        "We accept most major dental insurance plans.",
        "Our clinic is located at 123 Main Street, Suite 100, New York, NY 10001. We are near the city center with free parking available.",  # ← Location
        "Please call us at (555) 123-4567 for appointments.",
        "We offer general dentistry, cosmetic dentistry, and emergency services."
    ]
        
    print(f"\n📄 Created {len(test_docs)} test documents")
    
    # ──────────────────────────────────────────────
    # 4. Chunk the documents
    # ──────────────────────────────────────────────
    all_chunks = []
    for doc in test_docs:
        chunks = chunk_text(doc, chunk_size=200, overlap=20)
        all_chunks.extend(chunks)
    
    print(f"📝 Created {len(all_chunks)} chunks from test documents")
    
    # ──────────────────────────────────────────────
    # 5. Store chunks in Qdrant
    # ──────────────────────────────────────────────
    store_chunks_in_qdrant(
        client=client,
        collection_name="knowledge",
        tenant_id=tenant.id,
        chunks=all_chunks,
        source_name="test_faq.txt"
    )
    
    # ──────────────────────────────────────────────
    # 6. Test search
    # ──────────────────────────────────────────────
    print("\n🔍 Testing search...")
    query = "What are your hours?"
    results = search_similar_chunks(
        client=client,
        collection_name="knowledge",
        tenant_id=tenant.id,
        query_text=query,
        limit=3
    )
    
    print(f"Query: '{query}'")
    print("Results:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. Score: {r['score']:.3f} - {r['text'][:80]}...")
    
    # ──────────────────────────────────────────────
    # 7. Test isolation (Tenant B can't see Tenant A's data)
    # ──────────────────────────────────────────────
    print("\n🔒 Testing isolation...")
    tenant_b = db.query(Tenant).filter(Tenant.id != tenant.id).first()
    
    if tenant_b:
        results_b = search_similar_chunks(
            client=client,
            collection_name="knowledge",
            tenant_id=tenant_b.id,
            query_text=query,
            limit=3
        )
        print(f"Tenant B search results: {len(results_b)} chunks found (should be 0)")
        
        if len(results_b) == 0:
            print("✅ Isolation works! Tenant B cannot see Tenant A's data.")
        else:
            print("❌ Isolation failed! Tenant B can see Tenant A's data.")
    else:
        print("⚠️ No second tenant found. Create another tenant to test isolation.")
    
    db.close()
    
    print("\n" + "=" * 40)
    print("✅ Ingestion test completed!")

if __name__ == "__main__":
    test_ingestion()