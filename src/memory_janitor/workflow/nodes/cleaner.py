"""
Cleaner Node
============

Node 2: Filters noise from raw activities using LLM.
"""

import json

from memory_janitor.adapters.llm import get_llm_adapter
from memory_janitor.config import get_settings, load_prompt
from memory_janitor.domain.models import ActivityItem, CleanedItem, ProcessingStatus
from memory_janitor.logging import get_logger
from memory_janitor.workflow.state import WorkflowState

logger = get_logger(__name__)


def _build_cleaning_prompt(items: list[ActivityItem]) -> str:
    """Build prompt for batch cleaning."""
    items_text = "\n\n".join([
        f"[Item {i+1}]\n"
        f"Source: {item.source_type}\n"
        f"Application: {item.application or 'Unknown'}\n"
        f"Content: {item.content[:500]}..."
        if len(item.content) > 500 else
        f"[Item {i+1}]\n"
        f"Source: {item.source_type}\n"
        f"Application: {item.application or 'Unknown'}\n"
        f"Content: {item.content}"
        for i, item in enumerate(items)
    ])
    
    return f"""Analyze the following activity items and determine which ones contain valuable information worth remembering.

{items_text}

For each item, respond with a JSON array where each element has:
- "item_index": the item number (1-based)
- "decision": "KEEP" or "DISCARD"
- "reason": brief explanation

Example response:
[
  {{"item_index": 1, "decision": "KEEP", "reason": "Contains technical decision about caching"}},
  {{"item_index": 2, "decision": "DISCARD", "reason": "Social media browsing"}}
]

Respond ONLY with the JSON array, no other text."""


def _parse_cleaning_response(
    response: str,
    items: list[ActivityItem],
) -> list[CleanedItem]:
    """Parse LLM response into CleanedItem list."""
    cleaned = []
    
    try:
        # Extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            # Remove markdown code blocks
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        decisions = json.loads(response)
        
        # Create a map for quick lookup
        decision_map = {d["item_index"]: d for d in decisions}
        
        for i, item in enumerate(items):
            idx = i + 1
            if idx in decision_map:
                d = decision_map[idx]
                cleaned.append(CleanedItem(
                    original=item,
                    is_valuable=d["decision"].upper() == "KEEP",
                    clean_reason=d.get("reason", ""),
                ))
            else:
                # Default to keep if not in response
                cleaned.append(CleanedItem(
                    original=item,
                    is_valuable=True,
                    clean_reason="Not evaluated, kept by default",
                ))
                
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("cleaning_response_parse_failed", error=str(e))
        # On parse failure, keep all items
        for item in items:
            cleaned.append(CleanedItem(
                original=item,
                is_valuable=True,
                clean_reason="Parse error, kept by default",
            ))
    
    return cleaned


async def cleaner_node(state: WorkflowState) -> dict:
    """
    Clean and filter raw activities.
    
    - Uses LLM to evaluate each item
    - Marks items as valuable or noise
    - Passes valuable items to next node
    """
    logger.info(
        "cleaner_node_started",
        batch_id=state.batch_id,
        item_count=len(state.raw_items),
    )
    
    if not state.raw_items:
        logger.info("cleaner_node_no_items", batch_id=state.batch_id)
        return {"status": ProcessingStatus.COMPLETED}
    
    settings = get_settings()
    llm = get_llm_adapter()
    
    # Load system prompt
    try:
        system_prompt = load_prompt(settings.pipeline.cleaner.prompt_file)
    except FileNotFoundError:
        system_prompt = "You are a noise filter for a personal memory system."
    
    # Process in batches
    batch_size = settings.pipeline.batch_size
    all_cleaned: list[CleanedItem] = []
    
    for i in range(0, len(state.raw_items), batch_size):
        batch = state.raw_items[i:i + batch_size]
        
        try:
            prompt = _build_cleaning_prompt(batch)
            response = await llm.generate(prompt, system_prompt=system_prompt)
            cleaned = _parse_cleaning_response(response, batch)
            all_cleaned.extend(cleaned)
            
        except Exception as e:
            logger.error("cleaner_batch_failed", error=str(e), batch_index=i)
            # On error, keep all items in batch
            for item in batch:
                all_cleaned.append(CleanedItem(
                    original=item,
                    is_valuable=True,
                    clean_reason=f"Error during cleaning: {str(e)}",
                ))
    
    # Count discarded
    valuable_count = sum(1 for c in all_cleaned if c.is_valuable)
    discarded_count = len(all_cleaned) - valuable_count
    
    logger.info(
        "cleaner_node_completed",
        batch_id=state.batch_id,
        valuable_count=valuable_count,
        discarded_count=discarded_count,
    )
    
    return {
        "status": ProcessingStatus.DEDUPLICATING,
        "cleaned_items": all_cleaned,
        "discarded_count": state.discarded_count + discarded_count,
    }
