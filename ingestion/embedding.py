# ingestion/embedding.py
import os
import sys

# ──────────────────────────────────────────────────────────────
# FORCE the cache path BEFORE anything else is imported
# ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(PROJECT_ROOT, "hf_cache")

# Set environment variables
os.environ["HF_HOME"] = CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = CACHE_DIR
os.environ["HUGGINGFACE_HUB_CACHE"] = CACHE_DIR

# Create the cache directory if it doesn't exist
os.makedirs(CACHE_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# NOW import the heavy libraries
# ──────────────────────────────────────────────────────────────
from sentence_transformers import SentenceTransformer

_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2', cache_folder=CACHE_DIR)
    return _MODEL

def get_embedding(text: str) -> list:
    model = get_model()
    embedding = model.encode(text)
    return embedding.tolist()

def get_embeddings_batch(texts: list) -> list:
    model = get_model()
    embeddings = model.encode(texts)
    return [e.tolist() for e in embeddings]

# Print cache location for debugging
print(f"📁 Using cache: {CACHE_DIR}")