"""
Reasoner Node
=============

Node 4: Classifies and prioritizes memories using LLM.
"""

import json

from memory_janitor.adapters.llm import get_llm_adapter
from memory_janitor.config import get_settings, load_prompt
from memory_janitor.domain.models import CleanedItem, MemoryFact, Priority, ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


def _build_reasoning_prompt(items: list[CleanedItem]) -> str:
    """Build prompt for batch classification."""
    items_text = "\n\n".join([
        f"[Item {i+1}]\n"
        f"Source: {item.original.source_type}\n"
        f"Application: {item.original.application or 'Unknown'}\n"
        f"Content: {item.original.content[:500]}..."
        if len(item.original.content) > 500 else
        f"[Item {i+1}]\n"
        f"Source: {item.original.source_type}\n"
        f"Application: {item.original.application or 'Unknown'}\n"
        f"Content: {item.original.content}"
        for i, item in enumerate(items)
    ])
    
    return f"""Classify the following activity items into memory categories.

{items_text}

For each item, respond with a JSON array where each element has:
- "item_index": the item number (1-based)
- "category": one of "core_decision", "tech_discovery", "user_preference", "project_milestone", "general_info"
- "priority": "high" or "low"
- "confidence": 0.0 to 1.0
- "summary": one-sentence summary suitable for memory storage
- "reason": brief explanation of classification

Example response:
[
  {{"item_index": 1, "category": "tech_discovery", "priority": "high", "confidence": 0.9, "summary": "Discovered Redis has better performance than Memcached for our use case", "reason": "Technical finding with practical implications"}}
]

Respond ONLY with the JSON array, no other text."""


def _parse_reasoning_response(
    response: str,
    items: list[CleanedItem],
    high_priority_categories: list[str],
) -> list[MemoryFact]:
    """Parse LLM response into MemoryFact list."""
    facts = []
    
    try:
        # Extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        classifications = json.loads(response)
        classification_map = {c["item_index"]: c for c in classifications}
        
        for i, item in enumerate(items):
            idx = i + 1
            if idx in classification_map:
                c = classification_map[idx]
                
                # Determine priority
                category = c.get("category", "general_info")
                priority_str = c.get("priority", "low")
                
                # Override priority based on category
                if category in high_priority_categories:
                    priority = Priority.HIGH
                else:
                    priority = Priority.HIGH if priority_str == "high" else Priority.LOW
                
                facts.append(MemoryFact(
                    content=c.get("summary", item.original.content[:200]),
                    category=category,
                    priority=priority,
                    confidence=float(c.get("confidence", 0.5)),
                    source_id=item.original.id,
                    source_type=item.original.source_type,
                    timestamp=item.original.timestamp,
                    project=_infer_project(item.original),
                    related_files=[item.original.file_path] if item.original.file_path else [],
                ))
            else:
                # Default classification for items not in response
                facts.append(MemoryFact(
                    content=item.original.content[:200],
                    category="general_info",
                    priority=Priority.LOW,
                    confidence=0.3,
                    source_id=item.original.id,
                    source_type=item.original.source_type,
                    timestamp=item.original.timestamp,
                ))
                
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("reasoning_response_parse_failed", error=str(e))
        # On parse failure, create basic facts
        for item in items:
            facts.append(MemoryFact(
                content=item.original.content[:200],
                category="general_info",
                priority=Priority.LOW,
                confidence=0.3,
                source_id=item.original.id,
                source_type=item.original.source_type,
                timestamp=item.original.timestamp,
            ))
    
    return facts


def _infer_project(item) -> str | None:
    """Try to infer project name from activity item."""
    # Try file path first
    if item.file_path:
        parts = item.file_path.split("/")
        # Look for common project indicators
        for i, part in enumerate(parts):
            if part in ("projects", "repos", "workspace", "src"):
                if i + 1 < len(parts):
                    return parts[i + 1]
    
    # Try window title
    if item.window_title:
        # Common patterns: "project-name - Editor" or "[project-name]"
        title = item.window_title
        if " - " in title:
            return title.split(" - ")[0].strip()
    
    return None


async def reasoner_node(state: WorkflowState) -> dict:
    """
    Classify and prioritize deduplicated items.
    
    - Uses LLM to classify each item
    - Assigns priority based on category
    - Creates MemoryFact objects for storage
    """
    logger.info(
        "reasoner_node_started",
        batch_id=state.batch_id,
        item_count=len(state.deduplicated_items),
    )
    
    if not state.deduplicated_items:
        logger.info("reasoner_node_no_items", batch_id=state.batch_id)
        return {"status": ProcessingStatus.COMPLETED}
    
    settings = get_settings()
    llm = get_llm_adapter()
    high_priority_categories = settings.pipeline.reasoner.high_priority_categories
    
    # Load system prompt
    try:
        system_prompt = load_prompt(settings.pipeline.reasoner.prompt_file)
    except FileNotFoundError:
        system_prompt = "You are a memory classifier for a personal knowledge management system."
    
    # Process in batches
    batch_size = settings.pipeline.batch_size
    all_facts: list[MemoryFact] = []
    
    for i in range(0, len(state.deduplicated_items), batch_size):
        batch = state.deduplicated_items[i:i + batch_size]
        
        try:
            prompt = _build_reasoning_prompt(batch)
            response = await llm.generate(prompt, system_prompt=system_prompt)
            facts = _parse_reasoning_response(response, batch, high_priority_categories)
            all_facts.extend(facts)
            
        except Exception as e:
            logger.error("reasoner_batch_failed", error=str(e), batch_index=i)
            # On error, create basic facts
            for item in batch:
                all_facts.append(MemoryFact(
                    content=item.original.content[:200],
                    category="general_info",
                    priority=Priority.LOW,
                    confidence=0.3,
                    source_id=item.original.id,
                    source_type=item.original.source_type,
                    timestamp=item.original.timestamp,
                ))
    
    high_priority_count = sum(1 for f in all_facts if f.priority == Priority.HIGH)
    
    logger.info(
        "reasoner_node_completed",
        batch_id=state.batch_id,
        total_facts=len(all_facts),
        high_priority_count=high_priority_count,
    )
    
    return {
        "status": ProcessingStatus.WRITING,
        "prioritized_items": all_facts,
    }
