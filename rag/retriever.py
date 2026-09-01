# rag/retriever.py
from qdrant_utils import get_qdrant_client
from ingestion.vector_store import search_similar_chunks

class Retriever:
    def __init__(self, collection_name: str = "knowledge"):
        self.client = get_qdrant_client()
        self.collection_name = collection_name
    
    def retrieve(self, tenant_id: int, query: str, top_k: int = 5) -> list:
        """Retrieve relevant chunks for a tenant"""
        results = search_similar_chunks(
            client=self.client,
            collection_name=self.collection_name,
            tenant_id=tenant_id,
            query_text=query,
            limit=top_k
        )
        return results