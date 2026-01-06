"""
Domain Models
=============

Core data structures representing the business domain.
These models are framework-agnostic and serializable.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Memory priority levels."""
    
    HIGH = "high"
    LOW = "low"


class ProcessingStatus(str, Enum):
    """Processing pipeline status."""
    
    PENDING = "pending"
    COLLECTING = "collecting"
    CLEANING = "cleaning"
    DEDUPLICATING = "deduplicating"
    REASONING = "reasoning"
    WRITING = "writing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActivityItem(BaseModel):
    """
    Raw activity item from Pieces OS.
    
    Represents unprocessed data captured from user's workflow.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: str = Field(description="e.g., 'workstream_event', 'ocr', 'browser'")
    content: str = Field(description="Raw content or OCR text")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Optional metadata from Pieces
    application: str | None = Field(default=None, description="Source application name")
    window_title: str | None = Field(default=None, description="Window or tab title")
    file_path: str | None = Field(default=None, description="Associated file path")
    url: str | None = Field(default=None, description="Associated URL")
    
    # Raw data for debugging
    raw_data: dict[str, Any] | None = Field(default=None, exclude=True)


class CleanedItem(BaseModel):
    """
    Cleaned activity item after noise filtering.
    
    Contains the original item plus cleaning metadata.
    """
    
    original: ActivityItem
    is_valuable: bool = Field(description="Whether this item passed noise filter")
    clean_reason: str = Field(description="Reason for keep/discard decision")
    
    @property
    def id(self) -> str:
        return self.original.id


class MemoryFact(BaseModel):
    """
    Distilled memory fact ready for storage.
    
    This is the final output of the processing pipeline.
    """
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(description="Atomic fact statement")
    category: str = Field(description="Classification category")
    priority: Priority = Field(default=Priority.LOW)
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    
    # Source tracking
    source_id: str = Field(description="Original ActivityItem ID")
    source_type: str
    timestamp: datetime
    
    # Rich metadata for Mem0
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Optional context
    project: str | None = Field(default=None)
    related_files: list[str] = Field(default_factory=list)
    
    def to_mem0_format(self) -> dict[str, Any]:
        """Convert to Mem0 API format."""
        return {
            "messages": [
                {"role": "user", "content": self.content}
            ],
            "metadata": {
                "source_type": self.source_type,
                "source_id": self.source_id,
                "category": self.category,
                "priority": self.priority.value,
                "confidence": self.confidence,
                "timestamp": self.timestamp.isoformat(),
                "project": self.project,
                "related_files": self.related_files,
                **self.metadata,
            }
        }


class ProcessingBatch(BaseModel):
    """
    A batch of items being processed through the pipeline.
    
    This is the State object for LangGraph workflow.
    """
    
    # Batch identification
    batch_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    
    # Pipeline data
    raw_items: list[ActivityItem] = Field(default_factory=list)
    cleaned_items: list[CleanedItem] = Field(default_factory=list)
    deduplicated_items: list[CleanedItem] = Field(default_factory=list)
    prioritized_items: list[MemoryFact] = Field(default_factory=list)
    
    # Results
    stored_count: int = Field(default=0)
    discarded_count: int = Field(default=0)
    duplicate_count: int = Field(default=0)
    error_count: int = Field(default=0)
    
    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Error tracking
    errors: list[str] = Field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float | None:
        """Calculate processing duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_summary(self) -> dict[str, Any]:
        """Generate a summary for dashboard display."""
        return {
            "batch_id": self.batch_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "raw_count": len(self.raw_items),
            "cleaned_count": len([c for c in self.cleaned_items if c.is_valuable]),
            "deduplicated_count": len(self.deduplicated_items),
            "stored_count": self.stored_count,
            "discarded_count": self.discarded_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
            "duration_seconds": self.duration_seconds,
        }
