# tests/test_isolation.py
from database import SessionLocal
from models import Tenant
from rag.pipeline import rag_answer

def test_isolation():
    print("🔒 Testing Multi-Tenant Isolation")
    print("=" * 50)
    
    db = SessionLocal()
    
    # Get both tenants
    tenant1 = db.query(Tenant).filter(Tenant.id == 1).first()
    tenant2 = db.query(Tenant).filter(Tenant.id == 2).first()
    
    if not tenant1 or not tenant2:
        print("❌ Both tenants not found. Run create_second_tenant.py first.")
        db.close()
        return
    
    print(f"✅ Tenant 1: {tenant1.name} (ID: {tenant1.id})")
    print(f"✅ Tenant 2: {tenant2.name} (ID: {tenant2.id})")
    
    # Test query
    query = "What are your hours?"
    
    print(f"\n🔍 Query: '{query}'")
    print("-" * 50)
    
    # Get answers
    answer1, _ = rag_answer(tenant1.id, query)
    answer2, _ = rag_answer(tenant2.id, query)
    
    print(f"\n1️⃣ {tenant1.name}:")
    print(f"   Answer: {answer1[:100]}...")
    
    print(f"\n2️⃣ {tenant2.name}:")
    print(f"   Answer: {answer2[:100]}...")
    
    # Check isolation
    print("\n" + "=" * 50)
    print("🔍 Isolation Check:")
    
    if "456 Oak Avenue" in answer1:
        print("❌ FAILED: Tenant 1 saw Tenant 2's data!")
    elif "123 Main Street" in answer2:
        print("❌ FAILED: Tenant 2 saw Tenant 1's data!")
    else:
        print("✅ PASSED: No cross-tenant data leakage detected!")
    
    db.close()

if __name__ == "__main__":
    test_isolation()