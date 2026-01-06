"""
Writer Node
===========

Node 5: Writes processed memories to Mem0.
"""

from datetime import datetime

from memory_janitor.adapters.mem0 import Mem0Adapter
from memory_janitor.domain.models import ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


async def writer_node(state: WorkflowState) -> dict:
    """
    Write prioritized memories to Mem0.
    
    - Stores each MemoryFact to Mem0
    - Handles errors gracefully
    - Updates counters
    """
    logger.info(
        "writer_node_started",
        batch_id=state.batch_id,
        item_count=len(state.prioritized_items),
    )
    
    if not state.prioritized_items:
        logger.info("writer_node_no_items", batch_id=state.batch_id)
        return {
            "status": ProcessingStatus.COMPLETED,
            "completed_at": datetime.now(),
        }
    
    mem0 = Mem0Adapter()
    
    stored_count = 0
    error_count = 0
    errors: list[str] = []
    
    for fact in state.prioritized_items:
        try:
            memory_id = await mem0.add(fact)
            
            if memory_id:
                stored_count += 1
                logger.debug(
                    "memory_stored",
                    memory_id=memory_id,
                    category=fact.category,
                    priority=fact.priority.value,
                )
            else:
                error_count += 1
                errors.append(f"Failed to store fact {fact.id}: No ID returned")
                
        except Exception as e:
            error_count += 1
            error_msg = f"Failed to store fact {fact.id}: {str(e)}"
            errors.append(error_msg)
            logger.error("writer_store_failed", fact_id=fact.id, error=str(e))
    
    logger.info(
        "writer_node_completed",
        batch_id=state.batch_id,
        stored_count=stored_count,
        error_count=error_count,
    )
    
    return {
        "status": ProcessingStatus.COMPLETED,
        "completed_at": datetime.now(),
        "stored_count": state.stored_count + stored_count,
        "error_count": state.error_count + error_count,
        "errors": errors,
    }
