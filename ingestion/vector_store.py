# ingestion/vector_store.py
import uuid
from qdrant_utils import get_qdrant_client
from qdrant_client.http import models
from .embedding import get_embedding

def store_chunks_in_qdrant(
    client,
    collection_name: str,
    tenant_id: int,
    chunks: list,
    source_name: str = "upload"
):
    """
    Store chunks in Qdrant with tenant_id payload for isolation.
    
    Args:
        client: Qdrant client instance
        collection_name: Name of the collection
        tenant_id: Tenant ID for filtering
        chunks: List of text chunks
        source_name: Source identifier (e.g., 'faq.pdf')
    """
    if not chunks:
        print("⚠️ No chunks to store")
        return
    
    points = []
    
    for i, chunk in enumerate(chunks):
        # Generate embedding
        vector = get_embedding(chunk)
        
        # Create point
        point = models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "tenant_id": tenant_id,
                "text": chunk,
                "chunk_id": i,
                "source": source_name,
                "chunk_size": len(chunk)
            }
        )
        points.append(point)
    
    # Upload to Qdrant
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    print(f"✅ Stored {len(points)} chunks for tenant {tenant_id}")


def search_similar_chunks(
    client,
    collection_name: str,
    tenant_id: int,
    query_text: str,
    limit: int = 5
) -> list:
    """
    Search for similar chunks for a specific tenant.
    """
    query_vector = get_embedding(query_text)
    
    # query_points is the new method name (replaces search)
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=tenant_id)
                )
            ]
        ),
        limit=limit
    )
    
    # Extract text from results
    chunks = []
    for point in results.points:
        chunks.append({
            "text": point.payload.get("text", ""),
            "score": point.score,
            "source": point.payload.get("source", "unknown")
        })
    
    return chunks