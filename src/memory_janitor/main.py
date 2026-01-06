"""
Main Entry Point
================

Application entry point with CLI support.
"""

import argparse
import asyncio
import signal
import sys
from typing import NoReturn

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from memory_janitor.config import get_settings
from memory_janitor.logging import get_logger, setup_logging
from memory_janitor.scheduler import start_scheduler, stop_scheduler
from memory_janitor.workflow import run_workflow

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="memory-janitor",
        description="Personal Memory Consolidation Agent",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run once command
    run_parser = subparsers.add_parser("run", help="Run processing once")
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    
    # Start daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Start as background daemon")
    daemon_parser.add_argument(
        "--no-scheduler",
        action="store_true",
        help="Disable scheduled processing",
    )
    
    # Dashboard command
    subparsers.add_parser("dashboard", help="Launch monitoring dashboard")
    
    # Status command
    subparsers.add_parser("status", help="Check service status")
    
    return parser.parse_args()


async def cmd_run(verbose: bool = False) -> int:
    """Run processing once."""
    logger.info("running_single_processing")
    
    try:
        result = await run_workflow()
        
        print("\n📊 Processing Result:")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Raw Items: {result.get('raw_count', 0)}")
        print(f"  Stored: {result.get('stored_count', 0)}")
        print(f"  Discarded: {result.get('discarded_count', 0)}")
        print(f"  Duplicates: {result.get('duplicate_count', 0)}")
        print(f"  Errors: {result.get('error_count', 0)}")
        
        return 0 if result.get("status") == "completed" else 1
        
    except Exception as e:
        logger.error("processing_failed", error=str(e))
        print(f"\n❌ Processing failed: {e}")
        return 1


async def cmd_daemon(no_scheduler: bool = False) -> NoReturn:
    """Run as background daemon."""
    logger.info("starting_daemon_mode")
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=sig.name)
        stop_scheduler()
        loop.stop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown_handler(s))
    
    # Start scheduler
    if not no_scheduler:
        start_scheduler()
        print("🚀 Memory Janitor daemon started")
        print("   Press Ctrl+C to stop")
    else:
        print("🚀 Memory Janitor daemon started (scheduler disabled)")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    
    sys.exit(0)


def cmd_dashboard() -> int:
    """Launch the dashboard."""
    from memory_janitor.dashboard import launch
    
    print("🖥️  Launching dashboard...")
    launch()
    return 0


async def cmd_status() -> int:
    """Check service status."""
    from memory_janitor.adapters.mem0 import Mem0Adapter
    from memory_janitor.adapters.pieces import PiecesAdapter
    
    print("\n🔍 Checking service status...\n")
    
    # Check Pieces OS
    pieces = PiecesAdapter()
    pieces_ok = await pieces.health_check()
    pieces_status = "🟢 Online" if pieces_ok else "🔴 Offline"
    print(f"  Pieces OS: {pieces_status}")
    
    # Check Mem0
    mem0 = Mem0Adapter()
    mem0_ok = await mem0.health_check()
    mem0_status = "🟢 Online" if mem0_ok else "🔴 Offline"
    print(f"  Mem0: {mem0_status}")
    
    # Check LLM
    settings = get_settings()
    llm_provider = settings.llm.provider
    llm_key_set = bool(
        settings.google_api_key if llm_provider == "gemini"
        else settings.anthropic_api_key
    )
    llm_status = "🟢 Configured" if llm_key_set else "🔴 API key not set"
    print(f"  LLM ({llm_provider}): {llm_status}")
    
    print()
    
    all_ok = pieces_ok and mem0_ok and llm_key_set
    if all_ok:
        print("✅ All services operational")
        return 0
    else:
        print("⚠️  Some services unavailable")
        return 1


def main() -> int:
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    # Parse arguments
    args = parse_args()
    
    if args.command == "run":
        return asyncio.run(cmd_run(verbose=args.verbose))
    
    elif args.command == "daemon":
        asyncio.run(cmd_daemon(no_scheduler=args.no_scheduler))
        return 0
    
    elif args.command == "dashboard":
        return cmd_dashboard()
    
    elif args.command == "status":
        return asyncio.run(cmd_status())
    
    else:
        # Default: show help
        print("Memory Janitor - Personal Memory Consolidation Agent")
        print()
        print("Usage:")
        print("  memory-janitor run        Run processing once")
        print("  memory-janitor daemon     Start as background daemon")
        print("  memory-janitor dashboard  Launch monitoring dashboard")
        print("  memory-janitor status     Check service status")
        print()
        print("Use --help for more options")
        return 0


if __name__ == "__main__":
    sys.exit(main())
