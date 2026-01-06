#!/bin/bash
# Memory Janitor Startup Script
# 一键启动前后端服务

set -e
cd "$(dirname "$0")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ 找不到虚拟环境，请先运行: python -m venv .venv && pip install -e .${NC}"
    exit 1
fi

PYTHON_EXEC=".venv/bin/python"

# 如果没有参数，默认启动 dashboard
if [ -z "$1" ]; then
    set -- "dashboard"
fi

# 启动 dashboard 前的预处理
if [ "$1" == "dashboard" ]; then
    echo -e "${YELLOW}🧹 清理端口 7860...${NC}"
    lsof -ti:7860 | xargs kill -9 2>/dev/null || true
    sleep 0.5
    
    echo -e "${YELLOW}🔍 检查服务状态...${NC}"
    $PYTHON_EXEC -m memory_janitor.main status || echo -e "${YELLOW}⚠️  部分服务未就绪，dashboard 仍可启动${NC}"
    echo ""
fi

# 执行命令
echo -e "${GREEN}🚀 启动服务: $@${NC}"
exec $PYTHON_EXEC -m memory_janitor.main "$@"
