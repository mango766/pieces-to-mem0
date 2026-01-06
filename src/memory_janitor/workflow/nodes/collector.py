"""
Collector Node
==============

Node 1: Fetches raw activity data from Pieces OS.
"""

from datetime import datetime

from memory_janitor.adapters.pieces import PiecesAdapter
from memory_janitor.domain.models import ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


async def collector_node(state: WorkflowState) -> dict:
    """
    Collect activities from Pieces OS.
    
    - Fetches incremental data since last checkpoint
    - Updates state with raw items
    - Saves new checkpoint on success
    """
    logger.info("collector_node_started", batch_id=state.batch_id)
    
    adapter = PiecesAdapter()
    
    # Check health first
    if not await adapter.health_check():
        error_msg = "Pieces OS is not available"
        logger.error("collector_node_failed", error=error_msg)
        return {
            "status": ProcessingStatus.FAILED,
            "errors": [error_msg],
            "error_count": state.error_count + 1,
        }
    
    # Get checkpoint for incremental fetch
    checkpoint = adapter.get_checkpoint()
    
    try:
        # Fetch activities
        raw_items = await adapter.fetch_activities(since=checkpoint)
        
        if not raw_items:
            logger.info("collector_node_no_data", batch_id=state.batch_id)
            return {
                "status": ProcessingStatus.COMPLETED,
                "started_at": datetime.now(),
                "completed_at": datetime.now(),
            }
        
        # Save new checkpoint (latest item timestamp)
        latest_timestamp = max(item.timestamp for item in raw_items)
        adapter.save_checkpoint(latest_timestamp)
        
        logger.info(
            "collector_node_completed",
            batch_id=state.batch_id,
            items_collected=len(raw_items),
        )
        
        return {
            "status": ProcessingStatus.CLEANING,
            "started_at": datetime.now(),
            "raw_items": raw_items,
        }
        
    except Exception as e:
        error_msg = f"Collection failed: {str(e)}"
        logger.error("collector_node_failed", error=error_msg)
        return {
            "status": ProcessingStatus.FAILED,
            "errors": [error_msg],
            "error_count": state.error_count + 1,
        }
