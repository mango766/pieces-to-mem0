"""
Task Scheduler
==============

APScheduler-based scheduler for periodic processing.
"""

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from memory_janitor.config import get_settings
from memory_janitor.logging import get_logger
from memory_janitor.workflow import run_workflow

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


async def _scheduled_job() -> None:
    """Job function called by scheduler."""
    logger.info("scheduled_job_started", timestamp=datetime.now().isoformat())
    
    try:
        result = await run_workflow()
        logger.info("scheduled_job_completed", **result)
    except Exception as e:
        logger.error("scheduled_job_failed", error=str(e))


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler."""
    global _scheduler
    
    settings = get_settings()
    
    _scheduler = AsyncIOScheduler(timezone=settings.scheduler.timezone)
    
    if settings.scheduler.enabled:
        # Add the main processing job
        _scheduler.add_job(
            _scheduled_job,
            trigger=IntervalTrigger(minutes=settings.scheduler.interval_minutes),
            id="memory_processing",
            name="Memory Processing Job",
            replace_existing=True,
        )
        
        logger.info(
            "scheduler_configured",
            interval_minutes=settings.scheduler.interval_minutes,
            timezone=settings.scheduler.timezone,
        )
    else:
        logger.info("scheduler_disabled")
    
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler."""
    global _scheduler
    
    if _scheduler is None:
        _scheduler = create_scheduler()
    
    if not _scheduler.running:
        _scheduler.start()
        logger.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    global _scheduler
    
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the current scheduler instance."""
    return _scheduler


def get_next_run_time() -> datetime | None:
    """Get the next scheduled run time."""
    if _scheduler:
        job = _scheduler.get_job("memory_processing")
        if job:
            return job.next_run_time
    return None
