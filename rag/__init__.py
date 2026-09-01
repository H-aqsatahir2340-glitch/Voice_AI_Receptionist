# rag/__init__.py
from .retriever import Retriever
from .prompt_builder import build_prompt

__all__ = ["Retriever", "build_prompt"]