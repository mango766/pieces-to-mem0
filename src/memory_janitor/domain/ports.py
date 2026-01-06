"""
Domain Ports (Interfaces)
=========================

Abstract interfaces that define how the domain interacts with external systems.
These are implemented by adapters in the integration layer.

Following Hexagonal Architecture (Ports and Adapters pattern).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from memory_janitor.domain.models import ActivityItem, MemoryFact


class ActivitySource(ABC):
    """
    Port for fetching activity data.
    
    Implemented by: PiecesAdapter
    """
    
    @abstractmethod
    async def fetch_activities(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ActivityItem]:
        """
        Fetch activities from the source.
        
        Args:
            since: Only fetch activities after this timestamp (for incremental sync)
            limit: Maximum number of activities to fetch
            
        Returns:
            List of raw activity items
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the activity source is available."""
        ...
    
    @abstractmethod
    def get_checkpoint(self) -> datetime | None:
        """Get the last processed timestamp."""
        ...
    
    @abstractmethod
    def save_checkpoint(self, timestamp: datetime) -> None:
        """Save the last processed timestamp."""
        ...


class MemoryStore(ABC):
    """
    Port for memory storage operations.
    
    Implemented by: Mem0Adapter
    """
    
    @abstractmethod
    async def add(
        self,
        fact: MemoryFact,
        user_id: str | None = None,
    ) -> str:
        """
        Add a memory fact to the store.
        
        Args:
            fact: The memory fact to store
            user_id: Optional user identifier
            
        Returns:
            The stored memory ID
        """
        ...
    
    @abstractmethod
    async def search(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for similar memories.
        
        Args:
            query: Search query
            user_id: Optional user identifier
            limit: Maximum results to return
            
        Returns:
            List of matching memories with scores
        """
        ...
    
    @abstractmethod
    async def update(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: ID of the memory to update
            content: New content
            metadata: Optional new metadata
            
        Returns:
            True if update succeeded
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the memory store is available."""
        ...


class LLMProvider(ABC):
    """
    Port for LLM operations.
    
    Implemented by: GeminiAdapter, AnthropicAdapter
    """
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate text using the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        ...
    
    @abstractmethod
    async def batch_generate(
        self,
        prompts: list[str],
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> list[str]:
        """
        Generate text for multiple prompts.
        
        Args:
            prompts: List of user prompts
            system_prompt: Shared system prompt
            temperature: Sampling temperature
            
        Returns:
            List of generated texts
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM provider is available."""
        ...
