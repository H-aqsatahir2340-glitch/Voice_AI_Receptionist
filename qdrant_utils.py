# qdrant_utils.py
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

def get_qdrant_client():
    """Get Qdrant client connection"""
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", 6333))
    return QdrantClient(host=host, port=port)

def create_collection_if_not_exists(collection_name: str = "knowledge"):
    """Create Qdrant collection if it doesn't exist"""
    client = get_qdrant_client()
    
    # Check if collection exists
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]
    
    if collection_name in collection_names:
        print(f"✅ Collection '{collection_name}' already exists")
        return client
    
    # Create collection WITHOUT payload_schema
    # We'll add tenant_id filtering using payload indexing separately
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=384,  # all-MiniLM-L6-v2 embedding size
            distance=models.Distance.COSINE
        )
    )
    
    # Create payload index for tenant_id (for faster filtering)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="tenant_id",
        field_schema=models.PayloadSchemaType.KEYWORD
    )
    
    print(f"✅ Collection '{collection_name}' created with tenant_id index")
    return client