# Pieces OS 调研报告

> **日期**: 2026-01-05  
> **状态**: 调研完成，待实际测试

---

## 1. 概述

### 1.1 什么是 Pieces OS

Pieces OS 是 Pieces for Developers 生态系统的**核心后端服务**，提供：

- **本地上下文存储**: 所有数据存储在本地设备，确保隐私
- **AI 集成基础**: 与本地 LLM 支持集成
- **工作流捕获**: 自动捕获屏幕活动、代码片段、浏览记录等
- **Workstream Pattern Engine (WPE)**: 视觉感知引擎，支持 OCR 和屏幕分析

### 1.2 与我们项目的关系

Pieces OS 是我们 Memory Janitor Agent 的**感知层数据源**，提供：
- Workstream Summaries（工作流摘要）
- OCR Text（截屏识别文本）
- Activity Metadata（应用名称、网页标题、文件路径）

---

## 2. 安装指南

### 2.1 下载 Pieces OS

**macOS 安装**:
1. 访问 [Pieces 官网](https://pieces.app/)
2. 点击 "Get Started" 或直接访问 [macOS 安装指南](https://docs.pieces.app/products/meet-pieces/macos-installation-guide)
3. 下载并安装 Pieces Desktop App（会自动安装 Pieces OS）

**或通过 Homebrew**:
```bash
# 待确认是否支持
brew install --cask pieces
```

### 2.2 验证安装

```bash
# 检查 Pieces OS 是否运行（macOS/Windows 默认端口 1000）
curl http://localhost:1000/.well-known/health
# 预期返回: ok
```

### 2.3 启用 Workstream Pattern Engine (WPE)

WPE 是视觉感知功能的核心，需要授权屏幕录制权限：

1. 打开 Pieces Desktop App
2. 进入设置 → Privacy & Permissions
3. 启用 "Workstream Pattern Engine"
4. 授予屏幕录制权限（系统偏好设置 → 隐私与安全 → 屏幕录制）

---

## 3. Python SDK 分析

### 3.1 安装

```bash
pip install pieces_os_client
```

**当前版本**: 5.0.0 (2025-12-10)  
**Python 兼容性**: 3.8 - 3.13

### 3.2 核心 API 模块

SDK 提供了丰富的 API，以下是与我们项目相关的核心模块：

#### 3.2.1 活动相关 API

| API 模块 | 主要方法 | 用途 |
|----------|----------|------|
| `ActivitiesApi` | `activities_snapshot()` | 获取所有活动快照 |
| `ActivityApi` | 单个活动操作 | 获取/更新单个活动 |

#### 3.2.2 Workstream 相关 API（核心）

| API 模块 | 主要方法 | 用途 |
|----------|----------|------|
| `WorkstreamEventsApi` | `workstream_events_snapshot()` | 获取工作流事件 |
| | `workstream_events_batch()` | 批量获取事件 |
| `WorkstreamSummariesApi` | `workstream_summaries_snapshot()` | 获取工作流摘要 |
| | `search_workstream_summaries()` | 搜索摘要 |

#### 3.2.3 Pattern Engine API（视觉感知）

| API 模块 | 主要方法 | 用途 |
|----------|----------|------|
| `WorkstreamPatternEngineApi` | `workstream_pattern_engine_processors_vision_events_snapshot()` | 获取视觉事件 |
| | `workstream_pattern_engine_processors_vision_events_search()` | 搜索视觉事件 |
| | `workstream_pattern_engine_processors_status()` | 获取引擎状态 |
| | `workstream_pattern_engine_processors_vision_status()` | 获取视觉处理器状态 |

#### 3.2.4 资源管理 API

| API 模块 | 主要方法 | 用途 |
|----------|----------|------|
| `AssetsApi` | `assets_snapshot()` | 获取所有代码片段 |
| `AssetApi` | 单个资源操作 | CRUD 操作 |

### 3.3 简化包装器 (推荐)

SDK 提供了 `PiecesClient` 包装器，简化常用操作：

```python
from pieces_os_client.wrapper import PiecesClient

# 初始化（默认连接 localhost:1000）
client = PiecesClient()

# 检查连接
print(client.is_pieces_running())  # True/False
print(client.version)              # Pieces OS 版本

# 获取所有代码片段
for asset in client.assets():
    print(f"Name: {asset.name}")

# 与 Copilot 对话
for response in client.copilot.stream_question("What is Python?"):
    print(response.question.answers.iterable[0].text, end="")

client.close()
```

### 3.4 底层 API 使用

对于更精细的控制，可以直接使用底层 API：

```python
import pieces_os_client
from pieces_os_client.api.workstream_events_api import WorkstreamEventsApi
from pieces_os_client.api.workstream_summaries_api import WorkstreamSummariesApi
from pieces_os_client.api.workstream_pattern_engine_api import WorkstreamPatternEngineApi

# 配置
configuration = pieces_os_client.Configuration(
    host="http://localhost:1000"
)

with pieces_os_client.ApiClient(configuration) as api_client:
    # 获取工作流事件
    events_api = WorkstreamEventsApi(api_client)
    events = events_api.workstream_events_snapshot()
    
    # 获取工作流摘要
    summaries_api = WorkstreamSummariesApi(api_client)
    summaries = summaries_api.workstream_summaries_snapshot()
    
    # 获取视觉事件（OCR 等）
    wpe_api = WorkstreamPatternEngineApi(api_client)
    vision_events = wpe_api.workstream_pattern_engine_processors_vision_events_snapshot()
```

---

## 4. 数据结构分析

### 4.1 Workstream Event

```python
WorkstreamEvent:
    id: str                    # 事件 ID
    created: GroupedTimestamp  # 创建时间
    updated: GroupedTimestamp  # 更新时间
    application: Application   # 关联应用
    metadata: dict             # 元数据
    # ... 其他字段
```

### 4.2 Workstream Summary

```python
WorkstreamSummary:
    id: str                    # 摘要 ID
    created: GroupedTimestamp  # 创建时间
    model: Model               # 使用的 LLM 模型
    summary: str               # 摘要文本
    events: list               # 关联的事件
    # ... 其他字段
```

### 4.3 Vision Event（OCR 数据）

```python
VisionEvent:
    id: str                    # 事件 ID
    created: GroupedTimestamp  # 创建时间
    ocr: OCRResult             # OCR 识别结果
    application: Application   # 来源应用
    window: Window             # 窗口信息
    # ... 其他字段
```

---

## 5. 关键发现

### 5.1 ✅ 支持的功能

| 功能 | 支持情况 | API |
|------|----------|-----|
| 获取工作流事件 | ✅ 支持 | `WorkstreamEventsApi.workstream_events_snapshot()` |
| 获取工作流摘要 | ✅ 支持 | `WorkstreamSummariesApi.workstream_summaries_snapshot()` |
| 搜索摘要 | ✅ 支持 | `WorkstreamSummariesApi.search_workstream_summaries()` |
| 获取 OCR/视觉事件 | ✅ 支持 | `WorkstreamPatternEngineApi.workstream_pattern_engine_processors_vision_events_snapshot()` |
| 搜索视觉事件 | ✅ 支持 | `WorkstreamPatternEngineApi.workstream_pattern_engine_processors_vision_events_search()` |
| 获取代码片段 | ✅ 支持 | `AssetsApi.assets_snapshot()` |
| 健康检查 | ✅ 支持 | `WellKnownApi.get_well_known_health()` |

### 5.2 ⚠️ 待确认的功能

| 功能 | 状态 | 说明 |
|------|------|------|
| Webhook 事件推送 | ❓ 待确认 | SDK 中未发现明显的 Webhook 注册 API |
| 增量数据查询 | ❓ 待测试 | 需要测试是否支持时间范围过滤 |
| 实时事件流 | ⚠️ 可能支持 | 发现 `stream_identifiers` 方法，待测试 |

### 5.3 ❌ 不支持或需要替代方案

| 功能 | 状态 | 替代方案 |
|------|------|----------|
| Webhook 推送 | 可能不支持 | 使用定时轮询 |

---

## 6. 集成方案

### 6.1 推荐的数据获取流程

```
1. 定时触发（每小时）
       │
       ▼
2. 调用 workstream_events_snapshot() 获取事件
       │
       ▼
3. 调用 workstream_summaries_snapshot() 获取摘要
       │
       ▼
4. 调用 vision_events_snapshot() 获取 OCR 数据
       │
       ▼
5. 合并数据，传入 LangGraph 工作流
```

### 6.2 增量获取策略

由于 Webhook 可能不支持，采用以下策略：

1. **记录 Checkpoint**: 保存上次同步的时间戳
2. **全量获取 + 本地过滤**: 获取所有数据，本地按时间过滤
3. **或使用 Search API**: 如果支持时间范围查询

### 6.3 Collector 节点实现思路

```python
class PiecesCollector:
    def __init__(self, host: str = "http://localhost:1000"):
        self.config = pieces_os_client.Configuration(host=host)
        
    def collect(self, since: datetime) -> list[RawItem]:
        """收集指定时间之后的数据"""
        items = []
        
        with pieces_os_client.ApiClient(self.config) as client:
            # 1. 获取工作流事件
            events_api = WorkstreamEventsApi(client)
            events = events_api.workstream_events_snapshot()
            items.extend(self._process_events(events, since))
            
            # 2. 获取工作流摘要
            summaries_api = WorkstreamSummariesApi(client)
            summaries = summaries_api.workstream_summaries_snapshot()
            items.extend(self._process_summaries(summaries, since))
            
            # 3. 获取视觉事件
            wpe_api = WorkstreamPatternEngineApi(client)
            vision = wpe_api.workstream_pattern_engine_processors_vision_events_snapshot()
            items.extend(self._process_vision(vision, since))
            
        return items
```

---

## 7. 下一步行动

### 7.1 立即行动

1. **安装 Pieces OS**: 下载并安装 Pieces Desktop App
2. **启用 WPE**: 授权屏幕录制权限
3. **运行测试脚本**: 验证 API 连接和数据获取

### 7.2 测试脚本

参见 `scripts/test_pieces_api.py`

### 7.3 待解决问题

| 问题 | 优先级 | 行动 |
|------|--------|------|
| 确认增量查询支持 | 高 | 测试 API 参数 |
| 确认 Webhook 支持 | 中 | 查阅更多文档或联系 Pieces 团队 |
| 测试数据量和性能 | 中 | 实际运行后评估 |

---

## 8. 参考资源

- [Pieces 官网](https://pieces.app/)
- [Pieces 文档](https://docs.pieces.app/)
- [Python SDK GitHub](https://github.com/pieces-app/pieces-os-client-sdk-for-python)
- [Python SDK PyPI](https://pypi.org/project/pieces-os-client/)
- [Discord 社区](https://discord.gg/getpieces)

---

**文档结束**
