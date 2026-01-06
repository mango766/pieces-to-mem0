"""
Integration Layer (Adapters)
============================

Implementations of domain ports for external services.
Each adapter encapsulates the details of interacting with a specific service.
"""

from memory_janitor.adapters.pieces import PiecesAdapter
from memory_janitor.adapters.mem0 import Mem0Adapter
from memory_janitor.adapters.llm import get_llm_adapter

__all__ = [
    "PiecesAdapter",
    "Mem0Adapter",
    "get_llm_adapter",
]
