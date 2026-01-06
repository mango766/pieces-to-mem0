#!/bin/bash
# Memory Janitor Startup Script

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Run the main application
python -m memory_janitor.main "$@"
