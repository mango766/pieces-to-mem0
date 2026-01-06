"""
Deduplicator Node
=================

Node 3: Checks for duplicate memories in Mem0.
"""

from memory_janitor.adapters.mem0 import Mem0Adapter
from memory_janitor.config import get_settings
from memory_janitor.domain.models import CleanedItem, ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


async def deduplicator_node(state: WorkflowState) -> dict:
    """
    Check for duplicates against existing memories.
    
    - Searches Mem0 for similar content
    - Filters out items that are too similar to existing memories
    - Passes unique items to next node
    """
    logger.info(
        "deduplicator_node_started",
        batch_id=state.batch_id,
        item_count=len(state.cleaned_items),
    )
    
    # Filter to only valuable items
    valuable_items = [c for c in state.cleaned_items if c.is_valuable]
    
    if not valuable_items:
        logger.info("deduplicator_node_no_items", batch_id=state.batch_id)
        return {"status": ProcessingStatus.COMPLETED}
    
    settings = get_settings()
    mem0 = Mem0Adapter()
    
    threshold = settings.pipeline.deduplicator.similarity_threshold
    search_limit = settings.pipeline.deduplicator.search_limit
    
    deduplicated: list[CleanedItem] = []
    duplicate_count = 0
    
    for item in valuable_items:
        try:
            # Search for similar memories
            results = await mem0.search(
                query=item.original.content[:200],  # Use first 200 chars for search
                limit=search_limit,
            )
            
            # Check if any result exceeds similarity threshold
            is_duplicate = False
            for result in results:
                score = result.get("score", 0)
                if score >= threshold:
                    is_duplicate = True
                    logger.debug(
                        "duplicate_found",
                        item_id=item.id,
                        existing_id=result.get("id"),
                        score=score,
                    )
                    break
            
            if not is_duplicate:
                deduplicated.append(item)
            else:
                duplicate_count += 1
                
        except Exception as e:
            logger.warning(
                "deduplication_check_failed",
                item_id=item.id,
                error=str(e),
            )
            # On error, keep the item (conservative approach)
            deduplicated.append(item)
    
    logger.info(
        "deduplicator_node_completed",
        batch_id=state.batch_id,
        unique_count=len(deduplicated),
        duplicate_count=duplicate_count,
    )
    
    return {
        "status": ProcessingStatus.REASONING,
        "deduplicated_items": deduplicated,
        "duplicate_count": state.duplicate_count + duplicate_count,
    }
