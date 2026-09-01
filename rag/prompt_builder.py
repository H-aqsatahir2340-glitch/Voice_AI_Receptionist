# rag/prompt_builder.py
# rag/prompt_builder.py

def build_prompt(query: str, chunks: list, tenant_info: dict, history: list = None) -> str:
    """
    Build a prompt with retrieved context, tenant info, and conversation history.
    """
    # Extract text from chunks
    context = "\n\n".join([f"- {c['text']}" for c in chunks])
    
    # Build history section
    history_text = ""
    if history:
        history_text = "\n\nPrevious conversation:\n"
        for msg in history[-6:]:  # Last 6 messages
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('content', '')}\n"
    
    # Build tenant info
    tenant_name = tenant_info.get("name", "the business")
    hours = tenant_info.get("hours", {})
    services = tenant_info.get("services", [])
    
    hours_text = ", ".join([f"{k}: {v}" for k, v in hours.items()]) if hours else "Not specified"
    services_text = ", ".join(services) if services else "General services"
    
    prompt = f"""You are a receptionist for {tenant_name}.

Business hours: {hours_text}
Services offered: {services_text}

{history_text}

Use the following information to answer the question. If the information doesn't contain the answer, say you don't know.

Context:
{context}

Question: {query}

Answer:"""
    
    return prompt