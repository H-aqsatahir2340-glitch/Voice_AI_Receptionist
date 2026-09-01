# chat_with_rag.py
from database import SessionLocal
from models import Tenant
from rag.pipeline import rag_answer

print("🤖 RAG Chatbot (Multi-Tenant)")
print("=" * 40)

# Get tenant
db = SessionLocal()
tenant = db.query(Tenant).first()
db.close()

if not tenant:
    print("❌ No tenant found.")
    exit()

print(f"💬 You are chatting with: {tenant.name}")
print("Type 'exit' to quit\n")

while True:
    query = input("👤 You: ")
    if query.lower() in ['exit', 'quit', 'bye']:
        print("👋 Goodbye!")
        break
    
    answer, chunks = rag_answer(tenant.id, query)
    print(f"🤖 AI: {answer}")
    print()