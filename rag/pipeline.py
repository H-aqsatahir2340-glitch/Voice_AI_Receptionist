# rag/pipeline.py
from database import SessionLocal
from models import Tenant, Configs
from rag import Retriever, build_prompt
from llm_handler import get_rag_response

def rag_answer(tenant_id: int, query: str, history: list = None):
    print(f"🔍 1. Received query: {query[:50]}...")
    
    db = SessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    if not tenant:
        db.close()
        print("❌ Tenant not found")
        return "Tenant not found", []
    
    print(f"✅ 2. Tenant found: {tenant.name}")
    
    # ──────────────────────────────────────────────
    # GET CONFIG FROM DATABASE (YOU WERE MISSING THIS)
    # ──────────────────────────────────────────────
    config = db.query(Configs).filter(Configs.tenant_id == tenant_id).first()
    
    # ──────────────────────────────────────────────
    # BUILD tenant_info WITH CONFIG
    # ──────────────────────────────────────────────
    tenant_info = {
        "name": tenant.name,
        "vertical": tenant.vertical,
        "hours": config.hours if config else {},
        "services": config.services if config else []
    }
    
    db.close()
    
    retriever = Retriever()
    chunks = retriever.retrieve(tenant_id, query, top_k=5)
    print(f"✅ 3. Found {len(chunks)} chunks")
    
    prompt = build_prompt(query, chunks, tenant_info, history)
    print(f"✅ 4. Prompt built: {len(prompt)} chars")
    
    try:
        response = get_rag_response(prompt)
        print(f"✅ 5. LLM response: {response[:50]}...")
        return response, chunks
    except Exception as e:
        print(f"❌ 6. LLM Error: {e}")
        return f"Error: {str(e)}", chunks