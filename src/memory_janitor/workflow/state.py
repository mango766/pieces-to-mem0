"""
Workflow State
==============

LangGraph state definition for the processing pipeline.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from memory_janitor.domain.models import (
    ActivityItem,
    CleanedItem,
    MemoryFact,
    ProcessingStatus,
)


def merge_items(left: list[Any], right: list[Any]) -> list[Any]:
    """Merge two lists, used for state updates."""
    return left + right


class WorkflowState(BaseModel):
    """
    LangGraph workflow state.
    
    This state flows through all nodes in the pipeline.
    Each node reads from and writes to specific fields.
    """
    
    # Batch identification
    batch_id: str = Field(default_factory=lambda: str(uuid4()))
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Pipeline data - each node processes and passes to next
    raw_items: Annotated[list[ActivityItem], merge_items] = Field(default_factory=list)
    cleaned_items: Annotated[list[CleanedItem], merge_items] = Field(default_factory=list)
    deduplicated_items: Annotated[list[CleanedItem], merge_items] = Field(default_factory=list)
    prioritized_items: Annotated[list[MemoryFact], merge_items] = Field(default_factory=list)
    
    # Counters
    stored_count: int = 0
    discarded_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    
    # Error tracking
    errors: Annotated[list[str], merge_items] = Field(default_factory=list)
    
    # Messages for LangGraph (optional, for debugging)
    messages: Annotated[list[Any], add_messages] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    def to_summary(self) -> dict[str, Any]:
        """Generate summary for dashboard."""
        duration = None
        if self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds()
        
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": duration,
            "raw_count": len(self.raw_items),
            "cleaned_count": len([c for c in self.cleaned_items if c.is_valuable]),
            "deduplicated_count": len(self.deduplicated_items),
            "prioritized_count": len(self.prioritized_items),
            "stored_count": self.stored_count,
            "discarded_count": self.discarded_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
        }
