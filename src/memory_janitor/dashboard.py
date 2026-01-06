"""
Gradio Dashboard
================

Monitoring dashboard for the Memory Janitor Agent.
Displays task status, processing history, and real-time logs.
Supports Chinese/English language switching.
"""

import asyncio
from datetime import datetime
from typing import Any, Generator

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import gradio as gr

from memory_janitor.adapters.mem0 import Mem0Adapter
from memory_janitor.adapters.pieces import PiecesAdapter
from memory_janitor.config import get_settings
from memory_janitor.logging import get_logger

logger = get_logger(__name__)

# Global state for dashboard
_processing_history: list[dict[str, Any]] = []
_current_task: dict[str, Any] | None = None
_log_buffer: list[str] = []
_max_log_lines = 100
_pipeline_logs: list[str] = []  # 流水线详细日志

# i18n translations
I18N = {
    "zh": {
        "title": "🧹 记忆管家 Dashboard",
        "subtitle": "个人记忆整合 Agent - Pieces OS → Mem0",
        "service_status": "### 服务状态",
        "pieces_os": "Pieces OS",
        "mem0": "Mem0",
        "overall": "整体状态",
        "online": "在线",
        "offline": "离线",
        "all_operational": "✅ 所有服务正常运行",
        "some_unavailable": "⚠️ 部分服务不可用",
        "refresh_status": "🔄 刷新状态",
        "manual_processing": "### 手动处理",
        "run_now": "▶️ 立即运行",
        "processing_history": "### 处理历史",
        "refresh_history": "🔄 刷新历史",
        "memory_stats": "### 记忆统计",
        "click_refresh": "*点击刷新加载*",
        "refresh_stats": "🔄 刷新统计",
        "recent_logs": "### 最近日志",
        "refresh_logs": "🔄 刷新日志",
        "no_history": "*暂无处理历史*",
        "no_logs": "*暂无日志*",
        "no_memories": "*暂无存储的记忆*",
        "total_memories": "记忆总数",
        "high_priority": "高优先级",
        "low_priority": "低优先级",
        "by_category": "### 按类别",
        "processing_result": "### 处理结果",
        "status": "状态",
        "raw_items": "原始条目",
        "stored": "已存储",
        "discarded": "已丢弃",
        "duplicates": "重复",
        "errors": "错误",
        "completed_at": "完成于",
        "failed": "失败",
        "manual_triggered": "手动处理已触发",
        "processing_completed": "处理完成",
        "memories_stored": "条记忆已存储",
        "processing_failed": "处理失败",
        "error_fetching": "获取统计信息出错",
        "table_time": "时间",
        "table_status": "状态",
        "table_raw": "原始",
        "table_stored": "存储",
        "table_discarded": "丢弃",
        "table_errors": "错误",
        "switch_lang": "🌐 English",
        "pipeline_title": "### 🔄 处理流水线",
        "pipeline_idle": "⏸️ 等待运行...",
        "node_collector": "📥 采集器",
        "node_cleaner": "🧹 清洗器",
        "node_deduplicator": "🔍 去重器",
        "node_reasoner": "🧠 推理器",
        "node_writer": "💾 写入器",
        "node_pending": "⏳ 等待中",
        "node_running": "🔄 运行中",
        "node_done": "✅ 完成",
        "node_skipped": "⏭️ 跳过",
        "pipeline_output": "### 📋 流水线输出",
    },
    "en": {
        "title": "🧹 Memory Janitor Dashboard",
        "subtitle": "Personal Memory Consolidation Agent - Pieces OS → Mem0",
        "service_status": "### Service Status",
        "pieces_os": "Pieces OS",
        "mem0": "Mem0",
        "overall": "Overall",
        "online": "Online",
        "offline": "Offline",
        "all_operational": "✅ All services operational",
        "some_unavailable": "⚠️ Some services unavailable",
        "refresh_status": "🔄 Refresh Status",
        "manual_processing": "### Manual Processing",
        "run_now": "▶️ Run Processing Now",
        "processing_history": "### Processing History",
        "refresh_history": "🔄 Refresh History",
        "memory_stats": "### Memory Statistics",
        "click_refresh": "*Click refresh to load*",
        "refresh_stats": "🔄 Refresh Stats",
        "recent_logs": "### Recent Logs",
        "refresh_logs": "🔄 Refresh Logs",
        "no_history": "*No processing history yet*",
        "no_logs": "*No logs yet*",
        "no_memories": "*No memories stored yet*",
        "total_memories": "Total Memories",
        "high_priority": "High Priority",
        "low_priority": "Low Priority",
        "by_category": "### By Category",
        "processing_result": "### Processing Result",
        "status": "Status",
        "raw_items": "Raw Items",
        "stored": "Stored",
        "discarded": "Discarded",
        "duplicates": "Duplicates",
        "errors": "Errors",
        "completed_at": "Completed at",
        "failed": "Failed",
        "manual_triggered": "Manual processing triggered",
        "processing_completed": "Processing completed",
        "memories_stored": "memories stored",
        "processing_failed": "Processing failed",
        "error_fetching": "Error fetching stats",
        "table_time": "Time",
        "table_status": "Status",
        "table_raw": "Raw",
        "table_stored": "Stored",
        "table_discarded": "Discarded",
        "table_errors": "Errors",
        "switch_lang": "🌐 中文",
        "pipeline_title": "### 🔄 Processing Pipeline",
        "pipeline_idle": "⏸️ Waiting to run...",
        "node_collector": "📥 Collector",
        "node_cleaner": "🧹 Cleaner",
        "node_deduplicator": "🔍 Deduplicator",
        "node_reasoner": "🧠 Reasoner",
        "node_writer": "💾 Writer",
        "node_pending": "⏳ Pending",
        "node_running": "🔄 Running",
        "node_done": "✅ Done",
        "node_skipped": "⏭️ Skipped",
        "pipeline_output": "### 📋 Pipeline Output",
    },
}

# Current language state
_current_lang = "zh"


def t(key: str) -> str:
    """Get translation for current language."""
    return I18N.get(_current_lang, I18N["zh"]).get(key, key)


def _add_log(message: str) -> None:
    """Add a log message to the buffer."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    _log_buffer.append(f"[{timestamp}] {message}")
    if len(_log_buffer) > _max_log_lines:
        _log_buffer.pop(0)


def _add_pipeline_log(message: str) -> None:
    """Add a pipeline log message."""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    _pipeline_logs.append(f"[{timestamp}] {message}")


def _clear_pipeline_logs() -> None:
    """Clear pipeline logs."""
    global _pipeline_logs
    _pipeline_logs = []


async def check_services_status() -> tuple[str, str, str]:
    """Check the status of Pieces OS and Mem0."""
    pieces_status = f"🔴 {t('offline')}"
    mem0_status = f"🔴 {t('offline')}"
    
    # Check Pieces OS
    pieces = PiecesAdapter()
    if await pieces.health_check():
        pieces_status = f"🟢 {t('online')} (Port 39300)"
    
    # Check Mem0
    mem0 = Mem0Adapter()
    if await mem0.health_check():
        mem0_status = f"🟢 {t('online')} (Cloud)"
    
    # Overall status
    if "🟢" in pieces_status and "🟢" in mem0_status:
        overall = t("all_operational")
    else:
        overall = t("some_unavailable")
    
    return pieces_status, mem0_status, overall


def get_status_display() -> str:
    """Get formatted status display."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        pieces, mem0, overall = loop.run_until_complete(check_services_status())
        return f"""
{t('service_status')}
- **{t('pieces_os')}**: {pieces}
- **{t('mem0')}**: {mem0}
- **{t('overall')}**: {overall}
"""
    finally:
        loop.close()


def _format_pipeline_status(current_node: str | None, completed: list[str], result: dict | None = None) -> str:
    """Format pipeline status as visual progress."""
    nodes = ["collector", "cleaner", "deduplicator", "reasoner", "writer"]
    node_names = {
        "collector": t("node_collector"),
        "cleaner": t("node_cleaner"),
        "deduplicator": t("node_deduplicator"),
        "reasoner": t("node_reasoner"),
        "writer": t("node_writer"),
    }
    
    lines = [t("pipeline_title"), ""]
    
    # Progress bar
    progress_parts = []
    for node in nodes:
        if node in completed:
            progress_parts.append(f"[✅ {node_names[node]}]")
        elif node == current_node:
            progress_parts.append(f"[🔄 {node_names[node]}]")
        else:
            progress_parts.append(f"[⏳ {node_names[node]}]")
    
    lines.append(" → ".join(progress_parts))
    lines.append("")
    
    # Node details
    for node in nodes:
        if node in completed:
            status = t("node_done")
        elif node == current_node:
            status = t("node_running")
        else:
            status = t("node_pending")
        lines.append(f"- **{node_names[node]}**: {status}")
    
    # Result summary if available
    if result:
        lines.append("")
        lines.append(f"**{t('processing_result')}**")
        lines.append(f"- {t('raw_items')}: {result.get('raw_count', 0)}")
        lines.append(f"- {t('stored')}: {result.get('stored_count', 0)}")
        lines.append(f"- {t('discarded')}: {result.get('discarded_count', 0)}")
        lines.append(f"- {t('duplicates')}: {result.get('duplicate_count', 0)}")
        lines.append(f"- {t('errors')}: {result.get('error_count', 0)}")
    
    return "\n".join(lines)


def _get_pipeline_output() -> str:
    """Get pipeline output logs."""
    if not _pipeline_logs:
        return "*等待运行...*" if _current_lang == "zh" else "*Waiting to run...*"
    return "```\n" + "\n".join(_pipeline_logs[-30:]) + "\n```"


async def run_workflow_with_logging() -> dict[str, Any]:
    """Run workflow with detailed logging for each step."""
    from memory_janitor.adapters.pieces import PiecesAdapter
    from memory_janitor.adapters.mem0 import Mem0Adapter
    from memory_janitor.adapters.llm import get_llm_adapter
    from memory_janitor.config import get_settings, load_prompt
    from memory_janitor.domain.models import CleanedItem, MemoryFact, Priority
    import json
    
    settings = get_settings()
    
    result = {
        "status": "completed",
        "raw_count": 0,
        "stored_count": 0,
        "discarded_count": 0,
        "duplicate_count": 0,
        "error_count": 0,
    }
    
    # Step 1: Collector
    _add_pipeline_log("=" * 50)
    _add_pipeline_log("📥 COLLECTOR: 开始从 Pieces OS 获取数据...")
    
    try:
        pieces = PiecesAdapter()
        activities = await pieces.fetch_activities(limit=50)
        result["raw_count"] = len(activities)
        
        _add_pipeline_log(f"📥 COLLECTOR: 获取到 {len(activities)} 条原始活动")
        for i, item in enumerate(activities[:5]):
            content_preview = item.content[:80].replace('\n', ' ')
            _add_pipeline_log(f"   [{i+1}] {item.source_type}: {content_preview}...")
        if len(activities) > 5:
            _add_pipeline_log(f"   ... 还有 {len(activities) - 5} 条")
    except Exception as e:
        _add_pipeline_log(f"❌ COLLECTOR ERROR: {e}")
        result["status"] = "failed"
        result["error_count"] += 1
        return result
    
    if not activities:
        _add_pipeline_log("📥 COLLECTOR: 没有新数据，流程结束")
        return result
    
    # Step 2: Cleaner
    _add_pipeline_log("")
    _add_pipeline_log("🧹 CLEANER: 开始 LLM 降噪处理...")
    
    cleaned_items: list[CleanedItem] = []
    try:
        llm = get_llm_adapter()
        try:
            system_prompt = load_prompt(settings.pipeline.cleaner.prompt_file)
        except FileNotFoundError:
            system_prompt = "You are a noise filter for a personal memory system."
        
        # Build prompt
        items_text = "\n\n".join([
            f"[Item {i+1}]\nSource: {item.source_type}\nContent: {item.content[:300]}"
            for i, item in enumerate(activities[:20])  # Limit to 20 items
        ])
        
        prompt = f"""Analyze these activity items. Decide which contain valuable information.

{items_text}

Respond with JSON array: [{{"item_index": 1, "decision": "KEEP/DISCARD", "reason": "..."}}]
Only JSON, no other text."""

        response = await llm.generate(prompt, system_prompt=system_prompt)
        _add_pipeline_log(f"🧹 CLEANER: LLM 响应长度 {len(response)} 字符")
        
        # Parse response
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        try:
            decisions = json.loads(response)
            decision_map = {d["item_index"]: d for d in decisions}
        except json.JSONDecodeError:
            _add_pipeline_log(f"🧹 CLEANER: JSON 解析失败，保留所有条目")
            decision_map = {}
        
        for i, item in enumerate(activities[:20]):
            idx = i + 1
            if idx in decision_map:
                d = decision_map[idx]
                is_valuable = d.get("decision", "").upper() == "KEEP"
                cleaned_items.append(CleanedItem(
                    original=item,
                    is_valuable=is_valuable,
                    clean_reason=d.get("reason", ""),
                ))
                if is_valuable:
                    _add_pipeline_log(f"   ✓ 保留: {item.content[:50]}...")
                else:
                    _add_pipeline_log(f"   ✗ 丢弃: {d.get('reason', 'N/A')}")
            else:
                cleaned_items.append(CleanedItem(original=item, is_valuable=True, clean_reason="默认保留"))
        
        valuable_items = [c for c in cleaned_items if c.is_valuable]
        result["discarded_count"] = len(cleaned_items) - len(valuable_items)
        _add_pipeline_log(f"🧹 CLEANER: 保留 {len(valuable_items)} 条，丢弃 {result['discarded_count']} 条")
        
    except Exception as e:
        _add_pipeline_log(f"❌ CLEANER ERROR: {e}")
        # 保留所有条目
        for item in activities[:20]:
            cleaned_items.append(CleanedItem(original=item, is_valuable=True, clean_reason="错误时默认保留"))
        valuable_items = cleaned_items
    
    if not valuable_items:
        _add_pipeline_log("🧹 CLEANER: 所有内容被过滤，流程结束")
        return result
    
    # Step 3: Deduplicator
    _add_pipeline_log("")
    _add_pipeline_log("🔍 DEDUPLICATOR: 开始语义去重...")
    
    deduped_items: list[CleanedItem] = []
    try:
        mem0 = Mem0Adapter()
        threshold = settings.pipeline.deduplicator.similarity_threshold
        
        for item in valuable_items:
            try:
                results = await mem0.search(query=item.original.content[:200], limit=3)
                is_duplicate = False
                for r in results:
                    score = r.get("score", 0)
                    if score >= threshold:
                        is_duplicate = True
                        _add_pipeline_log(f"   🔁 重复 (score={score:.2f}): {item.original.content[:40]}...")
                        break
                
                if not is_duplicate:
                    deduped_items.append(item)
            except Exception as e:
                _add_pipeline_log(f"   ⚠️ 去重检查失败: {e}")
                deduped_items.append(item)
        
        result["duplicate_count"] = len(valuable_items) - len(deduped_items)
        _add_pipeline_log(f"🔍 DEDUPLICATOR: 保留 {len(deduped_items)} 条，去除 {result['duplicate_count']} 条重复")
        
    except Exception as e:
        _add_pipeline_log(f"❌ DEDUPLICATOR ERROR: {e}")
        deduped_items = valuable_items
    
    if not deduped_items:
        _add_pipeline_log("🔍 DEDUPLICATOR: 所有内容重复，流程结束")
        return result
    
    # Step 4: Reasoner
    _add_pipeline_log("")
    _add_pipeline_log("🧠 REASONER: 开始分类和提取记忆...")
    
    facts: list[MemoryFact] = []
    try:
        llm = get_llm_adapter()
        try:
            system_prompt = load_prompt(settings.pipeline.reasoner.prompt_file)
        except FileNotFoundError:
            system_prompt = "You are a memory classifier."
        
        items_text = "\n\n".join([
            f"[Item {i+1}]\nContent: {item.original.content[:300]}"
            for i, item in enumerate(deduped_items[:10])
        ])
        
        prompt = f"""Classify these items into memory categories.

{items_text}

Categories: core_decision, tech_discovery, user_preference, project_milestone, general_info
Priority: high or low

Respond with JSON: [{{"item_index": 1, "category": "...", "priority": "high/low", "summary": "one sentence"}}]
Only JSON."""

        response = await llm.generate(prompt, system_prompt=system_prompt)
        _add_pipeline_log(f"🧠 REASONER: LLM 响应长度 {len(response)} 字符")
        
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        try:
            classifications = json.loads(response)
            class_map = {c["item_index"]: c for c in classifications}
        except json.JSONDecodeError:
            _add_pipeline_log(f"🧠 REASONER: JSON 解析失败，使用默认分类")
            class_map = {}
        
        for i, item in enumerate(deduped_items[:10]):
            idx = i + 1
            if idx in class_map:
                c = class_map[idx]
                category = c.get("category", "general_info")
                priority = Priority.HIGH if c.get("priority") == "high" else Priority.LOW
                summary = c.get("summary", item.original.content[:100])
                
                facts.append(MemoryFact(
                    content=summary,
                    category=category,
                    priority=priority,
                    confidence=0.8,
                    source_id=item.original.id,
                    source_type=item.original.source_type,
                    timestamp=item.original.timestamp,
                ))
                _add_pipeline_log(f"   [{category}|{priority.value}] {summary[:50]}...")
            else:
                facts.append(MemoryFact(
                    content=item.original.content[:100],
                    category="general_info",
                    priority=Priority.LOW,
                    confidence=0.5,
                    source_id=item.original.id,
                    source_type=item.original.source_type,
                    timestamp=item.original.timestamp,
                ))
        
        _add_pipeline_log(f"🧠 REASONER: 提取出 {len(facts)} 条结构化记忆")
        
    except Exception as e:
        _add_pipeline_log(f"❌ REASONER ERROR: {e}")
        result["error_count"] += 1
        # 创建基本 facts
        for item in deduped_items[:10]:
            facts.append(MemoryFact(
                content=item.original.content[:100],
                category="general_info",
                priority=Priority.LOW,
                confidence=0.3,
                source_id=item.original.id,
                source_type=item.original.source_type,
                timestamp=item.original.timestamp,
            ))
    
    if not facts:
        _add_pipeline_log("🧠 REASONER: 没有提取到有价值的记忆")
        return result
    
    # Step 5: Writer
    _add_pipeline_log("")
    _add_pipeline_log("💾 WRITER: 开始写入 Mem0...")
    
    try:
        mem0 = Mem0Adapter()
        stored = 0
        for fact in facts:
            try:
                memory_id = await mem0.add(fact)
                stored += 1
                _add_pipeline_log(f"   ✓ 已存储: {fact.content[:40]}... (ID: {memory_id[:8] if memory_id else 'N/A'})")
            except Exception as e:
                _add_pipeline_log(f"   ✗ 存储失败: {e}")
                result["error_count"] += 1
        
        result["stored_count"] = stored
        _add_pipeline_log(f"💾 WRITER: 成功存储 {stored} 条记忆到 Mem0")
    except Exception as e:
        _add_pipeline_log(f"❌ WRITER ERROR: {e}")
        result["error_count"] += 1
    
    _add_pipeline_log("")
    _add_pipeline_log("=" * 50)
    _add_pipeline_log(f"✅ 流程完成! 原始:{result['raw_count']} → 存储:{result['stored_count']}")
    
    return result


async def trigger_processing_with_viz() -> Generator[tuple[str, str, str], None, None]:
    """Trigger processing with real-time visualization updates."""
    global _current_task, _processing_history
    
    _clear_pipeline_logs()
    _add_log(t("manual_triggered"))
    _current_task = {"status": "running", "started_at": datetime.now().isoformat()}
    
    # Initial state
    yield (
        _format_pipeline_status("collector", []),
        _get_pipeline_output(),
        get_history_display(),
    )
    
    try:
        result = await run_workflow_with_logging()
        
        _current_task = None
        _processing_history.insert(0, {
            "timestamp": datetime.now().isoformat(),
            **result,
        })
        _processing_history = _processing_history[:20]
        
        _add_log(f"{t('processing_completed')}: {result.get('stored_count', 0)} {t('memories_stored')}")
        
        # Final state
        yield (
            _format_pipeline_status(None, ["collector", "cleaner", "deduplicator", "reasoner", "writer"], result),
            _get_pipeline_output(),
            get_history_display(),
        )
        
    except Exception as e:
        _current_task = None
        _add_log(f"{t('processing_failed')}: {str(e)}")
        _add_pipeline_log(f"❌ FATAL ERROR: {e}")
        
        yield (
            f"❌ {t('failed')}: {str(e)}",
            _get_pipeline_output(),
            get_history_display(),
        )


def get_history_display() -> str:
    """Get formatted processing history."""
    if not _processing_history:
        return t("no_history")
    
    lines = [
        f"| {t('table_time')} | {t('table_status')} | {t('table_raw')} | {t('table_stored')} | {t('table_discarded')} | {t('table_errors')} |",
        "|------|--------|-----|--------|-----------|--------|"
    ]
    
    for entry in _processing_history[:10]:
        timestamp = entry.get("timestamp", "")[:19]
        status = entry.get("status", "unknown")
        raw = entry.get("raw_count", 0)
        stored = entry.get("stored_count", 0)
        discarded = entry.get("discarded_count", 0)
        errors = entry.get("error_count", 0)
        
        status_icon = "✅" if status == "completed" else "❌"
        lines.append(f"| {timestamp} | {status_icon} | {raw} | {stored} | {discarded} | {errors} |")
    
    return "\n".join(lines)


def get_logs_display() -> str:
    """Get formatted log display."""
    if not _log_buffer:
        return t("no_logs")
    return "\n".join(_log_buffer[-50:])


async def get_memory_stats() -> str:
    """Get memory statistics from Mem0."""
    try:
        mem0 = Mem0Adapter()
        memories = await mem0.get_all(page_size=100)
        
        if not memories:
            return t("no_memories")
        
        # Count by category
        categories: dict[str, int] = {}
        priorities: dict[str, int] = {"high": 0, "low": 0}
        
        for mem in memories:
            metadata = mem.get("metadata", {})
            cat = metadata.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
            
            priority = metadata.get("priority", "low")
            priorities[priority] = priorities.get(priority, 0) + 1
        
        lines = [
            t("memory_stats"),
            f"- **{t('total_memories')}**: {len(memories)}",
            f"- **{t('high_priority')}**: {priorities['high']}",
            f"- **{t('low_priority')}**: {priorities['low']}",
            "",
            t("by_category"),
        ]
        
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat}: {count}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"*{t('error_fetching')}: {str(e)}*"


def switch_language() -> tuple:
    """Switch between Chinese and English."""
    global _current_lang
    _current_lang = "en" if _current_lang == "zh" else "zh"
    
    return (
        f"# {t('title')}",
        t("subtitle"),
        get_status_display(),
        t("refresh_status"),
        t("manual_processing"),
        t("run_now"),
        t("pipeline_title"),
        t("pipeline_output"),
        t("processing_history"),
        t("refresh_history"),
        t("memory_stats"),
        t("refresh_stats"),
        t("recent_logs"),
        t("refresh_logs"),
        t("switch_lang"),
    )


def create_dashboard() -> gr.Blocks:
    """Create the Gradio dashboard interface."""
    
    with gr.Blocks(title="Memory Janitor Dashboard", theme=gr.themes.Soft()) as dashboard:
        # Header with language switch
        with gr.Row():
            with gr.Column(scale=5):
                title_md = gr.Markdown(f"# {t('title')}")
                subtitle_md = gr.Markdown(t("subtitle"))
            with gr.Column(scale=1):
                lang_btn = gr.Button(t("switch_lang"), size="sm")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Service Status
                status_display = gr.Markdown(get_status_display())
                refresh_status_btn = gr.Button(t("refresh_status"), size="sm")
                
                # Manual Trigger
                manual_label = gr.Markdown(t("manual_processing"))
                trigger_btn = gr.Button(t("run_now"), variant="primary", size="lg")
            
            with gr.Column(scale=2):
                # Pipeline Visualization
                pipeline_label = gr.Markdown(t("pipeline_title"))
                pipeline_status = gr.Markdown(t("pipeline_idle"))
                
                # Pipeline Output
                output_label = gr.Markdown(t("pipeline_output"))
                pipeline_output = gr.Markdown("*等待运行...*")
        
        with gr.Row():
            with gr.Column():
                # Processing History
                history_label = gr.Markdown(t("processing_history"))
                history_display = gr.Markdown(get_history_display())
                refresh_history_btn = gr.Button(t("refresh_history"), size="sm")
            
            with gr.Column():
                # Memory Stats
                stats_label = gr.Markdown(t("memory_stats"))
                stats_display = gr.Markdown(t("click_refresh"))
                refresh_stats_btn = gr.Button(t("refresh_stats"), size="sm")
        
        with gr.Row():
            with gr.Column():
                # Logs
                logs_label = gr.Markdown(t("recent_logs"))
                logs_display = gr.Markdown(get_logs_display())
                refresh_logs_btn = gr.Button(t("refresh_logs"), size="sm")
        
        # Event handlers
        refresh_status_btn.click(
            fn=lambda: get_status_display(),
            outputs=status_display,
        )
        
        trigger_btn.click(
            fn=trigger_processing_with_viz,
            outputs=[pipeline_status, pipeline_output, history_display],
        )
        
        refresh_history_btn.click(
            fn=lambda: get_history_display(),
            outputs=history_display,
        )
        
        refresh_stats_btn.click(
            fn=get_memory_stats,
            outputs=stats_display,
        )
        
        refresh_logs_btn.click(
            fn=lambda: get_logs_display(),
            outputs=logs_display,
        )
        
        # Language switch handler
        lang_btn.click(
            fn=switch_language,
            outputs=[
                title_md,
                subtitle_md,
                status_display,
                refresh_status_btn,
                manual_label,
                trigger_btn,
                pipeline_label,
                output_label,
                history_label,
                refresh_history_btn,
                stats_label,
                refresh_stats_btn,
                logs_label,
                refresh_logs_btn,
                lang_btn,
            ],
        )
    
    return dashboard


def launch() -> None:
    """Launch the dashboard."""
    settings = get_settings()
    dashboard = create_dashboard()
    
    logger.info(
        "dashboard_launching",
        host=settings.dashboard.host,
        port=settings.dashboard.port,
    )
    
    dashboard.launch(
        server_name=settings.dashboard.host,
        server_port=settings.dashboard.port,
        share=settings.dashboard.share,
    )


if __name__ == "__main__":
    launch()
