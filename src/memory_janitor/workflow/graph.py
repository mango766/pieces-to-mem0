"""
LangGraph Workflow Definition
=============================

Defines the processing pipeline as a LangGraph StateGraph.
"""

from typing import Any

from langgraph.graph import END, StateGraph

from memory_janitor.domain.models import ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.nodes import (
    cleaner_node,
    collector_node,
    deduplicator_node,
    reasoner_node,
    writer_node,
)
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


def _should_continue(state: WorkflowState) -> str:
    """
    Routing function to determine next node.
    
    Returns the next node name or END based on state.
    """
    status = state.status
    
    # Check for failure or completion
    if status == ProcessingStatus.FAILED:
        return END
    if status == ProcessingStatus.COMPLETED:
        return END
    
    # Route based on current status
    status_to_node = {
        ProcessingStatus.PENDING: "collector",
        ProcessingStatus.COLLECTING: "collector",
        ProcessingStatus.CLEANING: "cleaner",
        ProcessingStatus.DEDUPLICATING: "deduplicator",
        ProcessingStatus.REASONING: "reasoner",
        ProcessingStatus.WRITING: "writer",
    }
    
    return status_to_node.get(status, END)


def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow.
    
    Pipeline:
        START -> Collector -> Cleaner -> Deduplicator -> Reasoner -> Writer -> END
    
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the graph
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("collector", collector_node)
    workflow.add_node("cleaner", cleaner_node)
    workflow.add_node("deduplicator", deduplicator_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("writer", writer_node)
    
    # Set entry point
    workflow.set_entry_point("collector")
    
    # Add edges (linear flow with conditional routing)
    workflow.add_conditional_edges(
        "collector",
        _should_continue,
        {
            "cleaner": "cleaner",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "cleaner",
        _should_continue,
        {
            "deduplicator": "deduplicator",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "deduplicator",
        _should_continue,
        {
            "reasoner": "reasoner",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "reasoner",
        _should_continue,
        {
            "writer": "writer",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "writer",
        _should_continue,
        {
            END: END,
        }
    )
    
    return workflow.compile()


async def run_workflow() -> dict[str, Any]:
    """
    Execute the workflow and return results.
    
    Returns:
        Summary dict of the processing batch
    """
    logger.info("workflow_started")
    
    # Create and compile workflow
    app = create_workflow()
    
    # Initialize state
    initial_state = WorkflowState()
    
    # Run the workflow
    try:
        final_state = await app.ainvoke(initial_state)
        
        # Convert to summary
        if isinstance(final_state, dict):
            summary = {
                "batch_id": final_state.get("batch_id", ""),
                "status": final_state.get("status", ProcessingStatus.COMPLETED).value,
                "raw_count": len(final_state.get("raw_items", [])),
                "stored_count": final_state.get("stored_count", 0),
                "discarded_count": final_state.get("discarded_count", 0),
                "duplicate_count": final_state.get("duplicate_count", 0),
                "error_count": final_state.get("error_count", 0),
            }
        else:
            summary = final_state.to_summary()
        
        logger.info("workflow_completed", **summary)
        return summary
        
    except Exception as e:
        logger.error("workflow_failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }
