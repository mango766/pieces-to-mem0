"""
Mem0 Adapter
============

Implements MemoryStore port for Mem0 integration.
Supports both cloud and local Mem0 deployments.
"""

from typing import Any

import httpx

from memory_janitor.config import get_settings
from memory_janitor.domain.models import MemoryFact
from memory_janitor.domain.ports import MemoryStore
from memory_janitor.logging import get_logger

logger = get_logger(__name__)


class Mem0Adapter(MemoryStore):
    """
    Adapter for Mem0 API.
    
    Handles memory storage, search, and update operations.
    """
    
    def __init__(self) -> None:
        settings = get_settings()
        self.api_base = settings.mem0.api_base
        self.api_key = settings.mem0_api_key
        self.default_user_id = settings.mem0.default_user_id
        self.default_metadata = settings.mem0.metadata
        
        if not self.api_key:
            logger.warning("mem0_api_key_not_set")
    
    def _get_headers(self) -> dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def health_check(self) -> bool:
        """Check if Mem0 API is available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Try to list memories (with limit=1) as health check
                response = await client.get(
                    f"{self.api_base}/memories/",
                    headers=self._get_headers(),
                    params={"user_id": self.default_user_id, "page_size": 1},
                )
                return response.status_code in (200, 401)  # 401 means API is up but key is wrong
        except Exception as e:
            logger.warning("mem0_health_check_failed", error=str(e))
            return False
    
    async def add(
        self,
        fact: MemoryFact,
        user_id: str | None = None,
    ) -> str:
        """Add a memory fact to Mem0."""
        user_id = user_id or self.default_user_id
        
        # Prepare payload
        payload = fact.to_mem0_format()
        payload["user_id"] = user_id
        
        # Merge default metadata
        if self.default_metadata:
            payload["metadata"] = {**self.default_metadata, **payload.get("metadata", {})}
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/memories/",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract memory ID from response
                memory_id = ""
                if isinstance(result, list) and result:
                    memory_id = result[0].get("id", result[0].get("event_id", ""))
                elif isinstance(result, dict):
                    memory_id = result.get("id", result.get("event_id", ""))
                
                logger.info(
                    "memory_added",
                    memory_id=memory_id,
                    category=fact.category,
                    priority=fact.priority.value,
                )
                
                return memory_id
                
        except httpx.HTTPStatusError as e:
            logger.error(
                "mem0_add_failed",
                status_code=e.response.status_code,
                detail=e.response.text,
            )
            raise
        except Exception as e:
            logger.error("mem0_add_failed", error=str(e))
            raise
    
    async def search(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for similar memories."""
        user_id = user_id or self.default_user_id
        
        payload = {
            "query": query,
            "user_id": user_id,
            "limit": limit,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/memories/search/",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                results = response.json()
                
                logger.debug(
                    "memory_search_completed",
                    query=query[:50],
                    result_count=len(results) if isinstance(results, list) else 0,
                )
                
                return results if isinstance(results, list) else []
                
        except Exception as e:
            logger.error("mem0_search_failed", error=str(e))
            return []
    
    async def update(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing memory."""
        payload: dict[str, Any] = {"text": content}
        if metadata:
            payload["metadata"] = metadata
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.put(
                    f"{self.api_base}/memories/{memory_id}/",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                
                logger.info("memory_updated", memory_id=memory_id)
                return True
                
        except Exception as e:
            logger.error("mem0_update_failed", memory_id=memory_id, error=str(e))
            return False
    
    async def get_all(
        self,
        user_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Get all memories for a user."""
        user_id = user_id or self.default_user_id
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_base}/memories/",
                    headers=self._get_headers(),
                    params={
                        "user_id": user_id,
                        "page": page,
                        "page_size": page_size,
                    },
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error("mem0_get_all_failed", error=str(e))
            return []
