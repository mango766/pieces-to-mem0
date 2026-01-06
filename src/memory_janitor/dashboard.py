"""
Gradio Dashboard
================

Monitoring dashboard for the Memory Janitor Agent.
Displays task status, processing history, and real-time logs.
Supports Chinese/English language switching.
"""

import asyncio
from datetime import datetime
from typing import Any

import gradio as gr

from memory_janitor.adapters.mem0 import Mem0Adapter
from memory_janitor.adapters.pieces import PiecesAdapter
from memory_janitor.config import get_settings
from memory_janitor.logging import get_logger
from memory_janitor.workflow import run_workflow

logger = get_logger(__name__)

# Global state for dashboard
_processing_history: list[dict[str, Any]] = []
_current_task: dict[str, Any] | None = None
_log_buffer: list[str] = []
_max_log_lines = 100

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


async def trigger_processing() -> tuple[str, str, str]:
    """Manually trigger the processing workflow."""
    global _current_task, _processing_history
    
    _add_log(t("manual_triggered"))
    _current_task = {"status": "running", "started_at": datetime.now().isoformat()}
    
    try:
        result = await run_workflow()
        
        _current_task = None
        _processing_history.insert(0, {
            "timestamp": datetime.now().isoformat(),
            **result,
        })
        
        # Keep only last 20 entries
        _processing_history = _processing_history[:20]
        
        _add_log(f"{t('processing_completed')}: {result.get('stored_count', 0)} {t('memories_stored')}")
        
        # Format result
        status_msg = f"✅ {t('completed_at')} {datetime.now().strftime('%H:%M:%S')}"
        result_msg = f"""
{t('processing_result')}
- **{t('status')}**: {result.get('status', 'unknown')}
- **{t('raw_items')}**: {result.get('raw_count', 0)}
- **{t('stored')}**: {result.get('stored_count', 0)}
- **{t('discarded')}**: {result.get('discarded_count', 0)}
- **{t('duplicates')}**: {result.get('duplicate_count', 0)}
- **{t('errors')}**: {result.get('error_count', 0)}
"""
        
        return status_msg, result_msg, get_history_display()
        
    except Exception as e:
        _current_task = None
        _add_log(f"{t('processing_failed')}: {str(e)}")
        return f"❌ {t('failed')}: {str(e)}", "", get_history_display()


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


def switch_language() -> tuple[str, str, str, str, str, str, str, str, str, str, str, str]:
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
    
    with gr.Blocks(title="Memory Janitor Dashboard") as dashboard:
        # Header with language switch
        with gr.Row():
            with gr.Column(scale=5):
                title_md = gr.Markdown(f"# {t('title')}")
                subtitle_md = gr.Markdown(t("subtitle"))
            with gr.Column(scale=1):
                lang_btn = gr.Button(t("switch_lang"), size="sm")
        
        with gr.Row():
            with gr.Column(scale=2):
                # Service Status
                status_display = gr.Markdown(get_status_display())
                refresh_status_btn = gr.Button(t("refresh_status"), size="sm")
                
                # Manual Trigger
                manual_label = gr.Markdown(t("manual_processing"))
                trigger_btn = gr.Button(t("run_now"), variant="primary")
                trigger_status = gr.Markdown("")
                trigger_result = gr.Markdown("")
                
            with gr.Column(scale=3):
                # Processing History
                history_label = gr.Markdown(t("processing_history"))
                history_display = gr.Markdown(get_history_display())
                refresh_history_btn = gr.Button(t("refresh_history"), size="sm")
        
        with gr.Row():
            with gr.Column():
                # Memory Stats
                stats_label = gr.Markdown(t("memory_stats"))
                stats_display = gr.Markdown(t("click_refresh"))
                refresh_stats_btn = gr.Button(t("refresh_stats"), size="sm")
            
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
            fn=trigger_processing,
            outputs=[trigger_status, trigger_result, history_display],
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
