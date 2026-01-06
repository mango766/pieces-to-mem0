"""
Pieces OS Adapter
=================

Implements ActivitySource port for Pieces OS integration.
Fetches workstream events, summaries, and OCR data.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from memory_janitor.config import DATA_DIR, get_settings
from memory_janitor.domain.models import ActivityItem
from memory_janitor.domain.ports import ActivitySource
from memory_janitor.logging import get_logger

logger = get_logger(__name__)


class PiecesAdapter(ActivitySource):
    """
    Adapter for Pieces OS API.
    
    Fetches activity data from the local Pieces OS instance.
    """
    
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.pieces.base_url
        self.timeout = settings.pieces.timeout
        self.checkpoint_path = DATA_DIR / "pieces_checkpoint.json"
        
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    async def health_check(self) -> bool:
        """Check if Pieces OS is running."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/.well-known/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning("pieces_health_check_failed", error=str(e))
            return False
    
    async def fetch_activities(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[ActivityItem]:
        """
        Fetch activities from Pieces OS.
        
        Aggregates data from multiple endpoints:
        - /workstream_events
        - /workstream_summaries
        - /activities
        """
        items: list[ActivityItem] = []
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Fetch workstream events
            events = await self._fetch_workstream_events(client, since)
            items.extend(events)
            
            # Fetch workstream summaries
            summaries = await self._fetch_workstream_summaries(client, since)
            items.extend(summaries)
            
            # Fetch activities
            activities = await self._fetch_activities(client, since)
            items.extend(activities)
        
        # Sort by timestamp
        items.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            items = items[:limit]
        
        logger.info(
            "pieces_activities_fetched",
            count=len(items),
            since=since.isoformat() if since else None,
        )
        
        return items
    
    async def _fetch_workstream_events(
        self,
        client: httpx.AsyncClient,
        since: datetime | None,
    ) -> list[ActivityItem]:
        """Fetch workstream events."""
        try:
            response = await client.get(f"{self.base_url}/workstream_events")
            response.raise_for_status()
            data = response.json()
            
            items = []
            for event in data.get("iterable", []):
                item = self._parse_workstream_event(event)
                if item and (since is None or item.timestamp > since):
                    items.append(item)
            
            return items
            
        except Exception as e:
            logger.error("fetch_workstream_events_failed", error=str(e))
            return []
    
    async def _fetch_workstream_summaries(
        self,
        client: httpx.AsyncClient,
        since: datetime | None,
    ) -> list[ActivityItem]:
        """Fetch workstream summaries."""
        try:
            response = await client.get(f"{self.base_url}/workstream_summaries")
            response.raise_for_status()
            data = response.json()
            
            items = []
            for summary in data.get("iterable", []):
                item = self._parse_workstream_summary(summary)
                if item and (since is None or item.timestamp > since):
                    items.append(item)
            
            return items
            
        except Exception as e:
            logger.error("fetch_workstream_summaries_failed", error=str(e))
            return []
    
    async def _fetch_activities(
        self,
        client: httpx.AsyncClient,
        since: datetime | None,
    ) -> list[ActivityItem]:
        """Fetch activities."""
        try:
            response = await client.get(f"{self.base_url}/activities")
            response.raise_for_status()
            data = response.json()
            
            items = []
            for activity in data.get("iterable", []):
                item = self._parse_activity(activity)
                if item and (since is None or item.timestamp > since):
                    items.append(item)
            
            return items
            
        except Exception as e:
            logger.error("fetch_activities_failed", error=str(e))
            return []
    
    def _parse_workstream_event(self, event: dict[str, Any]) -> ActivityItem | None:
        """Parse a workstream event into ActivityItem."""
        try:
            # Extract timestamp
            created = event.get("created", {})
            timestamp_str = created.get("value")
            timestamp = (
                datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp_str
                else datetime.now()
            )
            
            # Extract content - try multiple fields
            content = ""
            if "summary" in event:
                summary = event["summary"]
                if isinstance(summary, dict):
                    content = summary.get("text", "")
                else:
                    content = str(summary)
            
            # Skip empty content
            if not content.strip():
                return None
            
            # Extract application info
            app_info = event.get("application", {})
            application = app_info.get("name")
            
            return ActivityItem(
                id=event.get("id", ""),
                source_type="workstream_event",
                content=content,
                timestamp=timestamp,
                application=application,
                raw_data=event,
            )
            
        except Exception as e:
            logger.warning("parse_workstream_event_failed", error=str(e))
            return None
    
    def _parse_workstream_summary(self, summary: dict[str, Any]) -> ActivityItem | None:
        """Parse a workstream summary into ActivityItem."""
        try:
            # Extract timestamp
            created = summary.get("created", {})
            timestamp_str = created.get("value")
            timestamp = (
                datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp_str
                else datetime.now()
            )
            
            # Extract content
            summary_obj = summary.get("summary", {})
            content = ""
            if isinstance(summary_obj, dict):
                content = summary_obj.get("text", "")
            else:
                content = str(summary_obj)
            
            if not content.strip():
                return None
            
            return ActivityItem(
                id=summary.get("id", ""),
                source_type="workstream_summary",
                content=content,
                timestamp=timestamp,
                raw_data=summary,
            )
            
        except Exception as e:
            logger.warning("parse_workstream_summary_failed", error=str(e))
            return None
    
    def _parse_activity(self, activity: dict[str, Any]) -> ActivityItem | None:
        """Parse an activity into ActivityItem."""
        try:
            # Extract timestamp
            created = activity.get("created", {})
            timestamp_str = created.get("value")
            timestamp = (
                datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if timestamp_str
                else datetime.now()
            )
            
            # Extract content from event or mechanism
            content = ""
            event = activity.get("event", {})
            if isinstance(event, dict):
                content = event.get("description", "") or event.get("name", "")
            
            if not content.strip():
                return None
            
            return ActivityItem(
                id=activity.get("id", ""),
                source_type="activity",
                content=content,
                timestamp=timestamp,
                raw_data=activity,
            )
            
        except Exception as e:
            logger.warning("parse_activity_failed", error=str(e))
            return None
    
    def get_checkpoint(self) -> datetime | None:
        """Get the last processed timestamp."""
        try:
            if self.checkpoint_path.exists():
                data = json.loads(self.checkpoint_path.read_text())
                timestamp_str = data.get("last_processed")
                if timestamp_str:
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning("get_checkpoint_failed", error=str(e))
        return None
    
    def save_checkpoint(self, timestamp: datetime) -> None:
        """Save the last processed timestamp."""
        try:
            data = {"last_processed": timestamp.isoformat()}
            self.checkpoint_path.write_text(json.dumps(data, indent=2))
            logger.debug("checkpoint_saved", timestamp=timestamp.isoformat())
        except Exception as e:
            logger.error("save_checkpoint_failed", error=str(e))
