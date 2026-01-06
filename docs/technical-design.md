# 技术方案：Memory Janitor Agent

> **版本**: 1.0  
> **日期**: 2026-01-05  
> **基于**: 需求规格书 v1.0

---

## 目录

1. [方案概述](#1-方案概述)
2. [系统架构设计](#2-系统架构设计)
3. [核心模块设计](#3-核心模块设计)
4. [数据流设计](#4-数据流设计)
5. [LangGraph 工作流设计](#5-langgraph-工作流设计)
6. [外部集成设计](#6-外部集成设计)
7. [配置管理设计](#7-配置管理设计)
8. [监控与可观测性设计](#8-监控与可观测性设计)
9. [错误处理与容错设计](#9-错误处理与容错设计)
10. [部署方案](#10-部署方案)
11. [技术风险与缓解](#11-技术风险与缓解)
12. [实施路线图](#12-实施路线图)

---

## 1. 方案概述

### 1.1 设计目标

| 目标 | 描述 | 优先级 |
|------|------|--------|
| **功能完整** | 实现感知→蒸馏→存储的完整链路 | P0 |
| **低侵入性** | 后台静默运行，不影响用户日常工作 | P0 |
| **可配置性** | LLM、触发频率、存储后端均可配置 | P1 |
| **可观测性** | 提供 Gradio 监控界面 | P1 |
| **可扩展性** | 便于后续增加数据源或存储后端 | P2 |

### 1.2 技术选型决策

| 决策点 | 选型 | 理由 |
|--------|------|------|
| 工作流框架 | LangGraph | 节点式编排，状态管理清晰，便于调试 |
| 语言 | Python 3.11+ | LangGraph 原生支持，生态丰富 |
| 异步模型 | asyncio | 非阻塞 IO，适合后台服务 |
| 配置格式 | YAML | 可读性好，支持注释 |
| 监控 UI | Gradio | 快速搭建，与 Python 无缝集成 |
| 调度器 | APScheduler | 轻量级，支持 cron 表达式 |

### 1.3 核心设计原则

1. **单一职责**: 每个节点只做一件事
2. **幂等性**: 重复执行不产生副作用
3. **可恢复性**: 支持从 checkpoint 恢复
4. **松耦合**: 外部依赖通过抽象接口隔离

---

## 2. 系统架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              表现层 (Presentation)                           │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   Gradio UI     │    │    CLI 命令     │    │  Webhook 端点   │         │
│  │   (监控/触发)    │    │  (手动触发)     │    │   (事件接收)    │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
└───────────┼──────────────────────┼──────────────────────┼───────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              调度层 (Scheduling)                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                      Trigger Manager                             │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │       │
│  │  │ScheduleTrigger│  │ManualTrigger │  │WebhookTrigger│           │       │
│  │  │  (APScheduler)│  │   (直接调用)  │  │  (FastAPI)   │           │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              业务层 (Business Logic)                         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    LangGraph Workflow                            │       │
│  │                                                                  │       │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │       │
│  │  │Collector │ → │ Cleaner  │ → │Deduplicator│ → │ Reasoner │     │       │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │       │
│  │                                                      │          │       │
│  │                                                      ▼          │       │
│  │                                               ┌──────────┐     │       │
│  │                                               │  Writer  │     │       │
│  │                                               └──────────┘     │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              集成层 (Integration)                            │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  Pieces Client  │    │   LLM Client    │    │   Mem0 Client   │         │
│  │   (数据采集)     │    │  (降噪/推理)    │    │   (存储/查重)    │         │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
└───────────┼──────────────────────┼──────────────────────┼───────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              外部服务 (External Services)                    │
│                                                                             │
│       Pieces OS              Gemini / Claude              Mem0              │
│      (localhost)               (API)                  (Cloud/Local)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件职责矩阵

| 组件 | 职责 | 依赖 | 被依赖 |
|------|------|------|--------|
| Gradio UI | 监控展示、手动触发 | Trigger Manager, State Store | - |
| Trigger Manager | 统一调度入口 | LangGraph Workflow | Gradio UI, CLI, Webhook |
| LangGraph Workflow | 业务流程编排 | 各 Node, State | Trigger Manager |
| Pieces Client | Pieces OS API 封装 | Pieces OS | Collector Node |
| LLM Client | 多 LLM 统一接口 | Gemini/Claude API | Cleaner, Reasoner Node |
| Mem0 Client | Mem0 SDK 封装 | Mem0 Service | Deduplicator, Writer Node |
| Checkpoint Store | 增量同步状态 | 本地文件系统 | Collector Node |
| Config Manager | 配置加载与热更新 | YAML 文件 | 所有组件 |

---

## 3. 核心模块设计

### 3.1 模块划分

```
src/
├── core/                       # 核心业务逻辑
│   ├── graph.py               # LangGraph 工作流定义
│   ├── state.py               # State 类型定义
│   └── nodes/                 # 节点实现
│       ├── collector.py
│       ├── cleaner.py
│       ├── deduplicator.py
│       ├── reasoner.py
│       └── writer.py
│
├── clients/                    # 外部服务客户端
│   ├── base.py                # 抽象基类
│   ├── pieces_client.py       # Pieces OS 封装
│   ├── llm_client.py          # LLM 统一接口
│   └── mem0_client.py         # Mem0 封装
│
├── triggers/                   # 触发器
│   ├── base.py                # 抽象基类
│   ├── scheduler.py           # 定时触发
│   ├── manual.py              # 手动触发
│   └── webhook.py             # Webhook 触发（预留）
│
├── ui/                         # 用户界面
│   └── gradio_app.py          # Gradio 监控
│
├── store/                      # 持久化存储
│   ├── checkpoint.py          # Checkpoint 管理
│   └── metrics.py             # 指标存储
│
├── config/                     # 配置管理
│   └── loader.py              # YAML 加载器
│
└── utils/                      # 工具函数
    ├── logger.py              # 日志
    └── helpers.py             # 通用工具
```

### 3.2 核心类设计

#### 3.2.1 State 设计

```
MemoryJanitorState
├── 输入数据
│   └── raw_items: list[RawItem]           # Pieces 原始数据
│
├── 中间状态
│   ├── cleaned_items: list[CleanedItem]   # 清洗后
│   ├── deduplicated_items: list[DeduplicatedItem]  # 去重后
│   └── prioritized_items: list[PrioritizedItem]    # 优先级标记后
│
├── 输出结果
│   ├── stored_count: int                  # 成功存储数
│   ├── discarded_count: int               # 丢弃数
│   └── updated_count: int                 # 更新数（冲突处理）
│
└── 元数据
    ├── batch_id: str                      # 批次 ID
    ├── start_time: datetime               # 开始时间
    ├── end_time: datetime                 # 结束时间
    └── node_metrics: dict[str, NodeMetric] # 各节点耗时/计数
```

#### 3.2.2 数据项结构演进

```
阶段 1: RawItem (Collector 输出)
┌─────────────────────────────────────────┐
│ id: str                                 │
│ content: str          # 原始文本        │
│ source_type: str      # 来源类型        │
│ timestamp: datetime   # 捕获时间        │
│ metadata: dict        # 原始元数据      │
│   ├── app_name        # 应用名          │
│   ├── window_title    # 窗口标题        │
│   └── file_path       # 文件路径（可选）│
└─────────────────────────────────────────┘
            │
            ▼ Cleaner
阶段 2: CleanedItem
┌─────────────────────────────────────────┐
│ ... (继承 RawItem 所有字段)             │
│ is_valuable: bool     # 是否有价值      │
│ clean_reason: str     # 清洗/保留原因   │
└─────────────────────────────────────────┘
            │
            ▼ Deduplicator
阶段 3: DeduplicatedItem
┌─────────────────────────────────────────┐
│ ... (继承 CleanedItem 所有字段)         │
│ is_duplicate: bool    # 是否重复        │
│ similar_memory_id: str # 相似记忆 ID    │
│ action: str           # "add" | "update" | "skip" │
└─────────────────────────────────────────┘
            │
            ▼ Reasoner
阶段 4: PrioritizedItem
┌─────────────────────────────────────────┐
│ ... (继承 DeduplicatedItem 所有字段)    │
│ priority: str         # "high" | "low"  │
│ category: str         # 类别            │
│ confidence: float     # 置信度 0-1      │
│ fact: str             # 原子化事实      │
│ project: str          # 关联项目        │
│ related_files: list   # 关联文件        │
└─────────────────────────────────────────┘
```

### 3.3 客户端抽象设计

#### 3.3.1 LLM Client 接口

```
LLMClient (抽象基类)
├── analyze(prompt: str, content: str) → AnalysisResult
├── batch_analyze(prompt: str, contents: list[str]) → list[AnalysisResult]
└── get_model_info() → ModelInfo

实现类:
├── GeminiClient
├── AnthropicClient
└── OpenAIClient (预留)

工厂方法:
LLMClientFactory.create(provider: str, config: dict) → LLMClient
```

#### 3.3.2 Mem0 Client 接口

```
Mem0Client
├── add(text: str, metadata: dict) → str (memory_id)
├── search(query: str, limit: int) → list[Memory]
├── update(memory_id: str, text: str, metadata: dict) → bool
├── delete(memory_id: str) → bool
└── get(memory_id: str) → Memory

配置切换:
├── CloudMem0Client (api_key 认证)
└── SelfHostedMem0Client (base_url 配置)
```

---

## 4. 数据流设计

### 4.1 主数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              触发事件                                        │
│                    (定时 / 手动 / Webhook)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Collector                                                                │
│                                                                             │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            │
│    │ 读取         │  →   │ 调用         │  →   │ 更新         │            │
│    │ Checkpoint   │      │ Pieces API   │      │ Checkpoint   │            │
│    │ (last_sync)  │      │ (增量数据)   │      │ (new_sync)   │            │
│    └──────────────┘      └──────────────┘      └──────────────┘            │
│                                    │                                        │
│                          raw_items (N 条)                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Cleaner                                                                  │
│                                                                             │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            │
│    │ 加载         │  →   │ LLM 批量     │  →   │ 过滤         │            │
│    │ 降噪提示词   │      │ 分析         │      │ 无价值项     │            │
│    └──────────────┘      └──────────────┘      └──────────────┘            │
│                                    │                                        │
│                        cleaned_items (M 条, M ≤ N)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Deduplicator                                                             │
│                                                                             │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            │
│    │ 遍历每条     │  →   │ Mem0         │  →   │ 标记         │            │
│    │ cleaned_item │      │ search()     │      │ 动作类型     │            │
│    └──────────────┘      └──────────────┘      └──────────────┘            │
│                                    │                                        │
│    动作类型:                                                                │
│    ├── add: 新记忆，直接添加                                                │
│    ├── update: 与现有记忆冲突，需更新                                       │
│    └── skip: 完全重复，跳过                                                 │
│                                                                             │
│                      deduplicated_items (K 条, K ≤ M)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Reasoner                                                                 │
│                                                                             │
│    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐            │
│    │ 加载         │  →   │ LLM 批量     │  →   │ 标记优先级   │            │
│    │ 推理提示词   │      │ 分析         │      │ + 原子化     │            │
│    └──────────────┘      └──────────────┘      └──────────────┘            │
│                                    │                                        │
│    输出:                                                                    │
│    ├── priority: high / low                                                 │
│    ├── category: decision / discovery / preference / milestone / other     │
│    ├── confidence: 0.0 - 1.0                                               │
│    ├── fact: 原子化事实字符串                                               │
│    ├── project: 关联项目名                                                  │
│    └── related_files: 关联文件列表                                          │
│                                                                             │
│                       prioritized_items (K 条)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Writer                                                                   │
│                                                                             │
│    ┌──────────────────────────────────────────────────────────────┐        │
│    │ 遍历 prioritized_items                                       │        │
│    │                                                              │        │
│    │    action == "add"    → Mem0.add(fact, metadata)            │        │
│    │    action == "update" → Mem0.update(memory_id, fact, meta)  │        │
│    │    action == "skip"   → 跳过                                 │        │
│    │                                                              │        │
│    └──────────────────────────────────────────────────────────────┘        │
│                                    │                                        │
│    结果统计:                                                                │
│    ├── stored_count: 新增数量                                               │
│    ├── updated_count: 更新数量                                              │
│    └── discarded_count: 丢弃数量                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              完成                                            │
│                    (更新指标 → 通知 Gradio UI)                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据量估算

| 阶段 | 预估数据量 | 说明 |
|------|------------|------|
| Collector 输出 | 50-200 条/小时 | 取决于用户活跃度 |
| Cleaner 输出 | 30-100 条/小时 | 约 50% 过滤率 |
| Deduplicator 输出 | 20-80 条/小时 | 约 20% 重复率 |
| Writer 写入 | 20-80 条/小时 | 最终存储量 |

### 4.3 Checkpoint 机制

```
checkpoint.json
┌─────────────────────────────────────────┐
│ {                                       │
│   "last_sync_time": "2026-01-05T14:00:00Z", │
│   "last_batch_id": "batch_20260105_140000", │
│   "pieces_cursor": "...",               │  # Pieces API 分页游标（如有）
│   "stats": {                            │
│     "total_processed": 1234,            │
│     "total_stored": 567,                │
│     "total_discarded": 667              │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘

更新时机:
├── Collector 成功获取数据后更新 last_sync_time
├── 整个批次完成后更新 stats
└── 失败时不更新（支持重试）
```

---

## 5. LangGraph 工作流设计

### 5.1 Graph 结构

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  collector  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌─────│  has_data?  │─────┐
              │     └─────────────┘     │
              │ Yes                     │ No
              ▼                         ▼
       ┌─────────────┐           ┌─────────────┐
       │   cleaner   │           │     END     │
       └──────┬──────┘           └─────────────┘
              │
              ▼
       ┌─────────────┐
       │ deduplicator│
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │  reasoner   │
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │   writer    │
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │     END     │
       └─────────────┘
```

### 5.2 条件边设计

| 边 | 条件 | 目标节点 |
|----|------|----------|
| collector → ? | `len(state.raw_items) > 0` | cleaner |
| collector → ? | `len(state.raw_items) == 0` | END |

### 5.3 节点设计详解

#### 5.3.1 Collector 节点

```
输入: State (空或上一批次残留)
输出: State with raw_items

逻辑:
1. 读取 checkpoint.last_sync_time
2. 调用 Pieces API 获取 [last_sync_time, now] 的数据
3. 转换为 RawItem 列表
4. 更新 state.raw_items
5. 记录 node_metrics (耗时、数量)

异常处理:
├── Pieces API 超时 → 记录日志，返回空列表
└── 数据格式错误 → 跳过该条，继续处理
```

#### 5.3.2 Cleaner 节点

```
输入: State with raw_items
输出: State with cleaned_items

逻辑:
1. 加载 config/prompts/cleaner.txt
2. 批量调用 LLM (每批 10 条，减少 API 调用)
3. 解析 LLM 返回的 JSON 结构
4. 过滤 is_valuable == false 的项
5. 更新 state.cleaned_items

LLM 输入格式:
┌─────────────────────────────────────────┐
│ System: {cleaner_prompt}                │
│ User:                                   │
│   请分析以下内容，判断是否有价值：        │
│   1. {content_1}                        │
│   2. {content_2}                        │
│   ...                                   │
└─────────────────────────────────────────┘

LLM 输出格式:
┌─────────────────────────────────────────┐
│ [                                       │
│   {"index": 1, "valuable": true, "reason": "..."}, │
│   {"index": 2, "valuable": false, "reason": "广告内容"}, │
│   ...                                   │
│ ]                                       │
└─────────────────────────────────────────┘
```

#### 5.3.3 Deduplicator 节点

```
输入: State with cleaned_items
输出: State with deduplicated_items

逻辑:
1. 遍历 cleaned_items
2. 对每条调用 Mem0.search(item.content, limit=3)
3. 判断相似度:
   ├── 无匹配 → action = "add"
   ├── 高相似 (>0.9) + 语义相同 → action = "skip"
   └── 中等相似 (0.7-0.9) + 语义冲突 → action = "update"
4. 更新 state.deduplicated_items

冲突判断策略:
┌─────────────────────────────────────────┐
│ 1. 向量相似度 (Mem0 search 返回)        │
│ 2. LLM 语义判断 (可选，高成本)          │
│    - 输入: 新内容 + 匹配到的旧内容       │
│    - 输出: same / update / different    │
└─────────────────────────────────────────┘
```

#### 5.3.4 Reasoner 节点

```
输入: State with deduplicated_items
输出: State with prioritized_items

逻辑:
1. 加载 config/prompts/reasoner.txt
2. 批量调用 LLM
3. 解析返回结果，提取:
   ├── priority
   ├── category
   ├── confidence
   ├── fact (原子化)
   ├── project
   └── related_files
4. 更新 state.prioritized_items

LLM 输出格式:
┌─────────────────────────────────────────┐
│ {                                       │
│   "priority": "high",                   │
│   "category": "decision",               │
│   "confidence": 0.92,                   │
│   "fact": "决定使用 Redis 替代 Memcached 作为缓存方案", │
│   "project": "e-commerce-backend",      │
│   "related_files": ["/src/cache/..."]   │
│ }                                       │
└─────────────────────────────────────────┘
```

#### 5.3.5 Writer 节点

```
输入: State with prioritized_items
输出: State with stored_count, updated_count, discarded_count

逻辑:
1. 遍历 prioritized_items
2. 根据 action 执行:
   ├── add → Mem0.add(fact, metadata)
   ├── update → Mem0.update(memory_id, fact, metadata)
   └── skip → 跳过
3. 统计结果
4. 更新 checkpoint

Metadata 构造:
┌─────────────────────────────────────────┐
│ {                                       │
│   "source_type": item.source_type,      │
│   "timestamp": item.timestamp,          │
│   "project": item.project,              │
│   "priority": item.priority,            │
│   "category": item.category,            │
│   "confidence": item.confidence,        │
│   "related_files": item.related_files   │
│ }                                       │
└─────────────────────────────────────────┘
```

---

## 6. 外部集成设计

### 6.1 Pieces OS 集成

#### 6.1.1 API 调研要点

| 调研项 | 说明 | 状态 |
|--------|------|------|
| SDK 安装 | `pip install pieces-os-client` | 待验证 |
| 认证方式 | 本地无需认证 / API Key | 待确认 |
| 数据端点 | 获取 Workstream、OCR、Metadata | 待调研 |
| 增量查询 | 是否支持时间范围过滤 | 待确认 |
| Webhook | 是否支持事件推送 | 待调研 |

#### 6.1.2 预期 API 调用

```
# 假设的 API 结构（待调研确认）

PiecesClient
├── get_activities(since: datetime) → list[Activity]
│   └── Activity:
│       ├── id
│       ├── type: "ocr" | "browser" | "code"
│       ├── content
│       ├── timestamp
│       └── metadata
│
├── get_workstream_summary(since: datetime) → list[Summary]
│
└── health_check() → bool
```

### 6.2 Mem0 集成

#### 6.2.1 SDK 使用

```
# Cloud 模式
from mem0 import MemoryClient
client = MemoryClient(api_key="...")

# Self-hosted 模式
from mem0 import Memory
client = Memory(base_url="http://localhost:8000")

# 统一接口
client.add(text, user_id, metadata)
client.search(query, user_id, limit)
client.update(memory_id, text, metadata)
```

#### 6.2.2 用户隔离

```
user_id 策略:
├── 单用户模式: 固定 user_id = "default_user"
└── 多用户模式（预留）: user_id = config.user_id
```

### 6.3 LLM 集成

#### 6.3.1 统一接口设计

```
LLMClient 抽象:
├── provider: str
├── model: str
├── analyze(system_prompt, user_prompt) → str
└── batch_analyze(system_prompt, user_prompts) → list[str]

实现:
├── GeminiClient
│   └── 使用 google-generativeai SDK
│
├── AnthropicClient
│   └── 使用 anthropic SDK
│
└── OpenAIClient (预留)
    └── 使用 openai SDK
```

#### 6.3.2 成本控制

| 策略 | 说明 |
|------|------|
| 批量处理 | 每批 10 条，减少 API 调用次数 |
| 模型选择 | 默认使用低成本模型 (Flash/Haiku) |
| 缓存 | 相同输入缓存结果（可选） |
| 限流 | 控制每分钟 API 调用上限 |

---

## 7. 配置管理设计

### 7.1 配置文件结构

```yaml
# config/config.yaml

# ===== 触发配置 =====
trigger:
  mode: "scheduled"          # scheduled | manual | webhook
  interval: 3600             # 定时间隔（秒）
  
# ===== Pieces OS 配置 =====
pieces:
  base_url: "http://localhost:1000"
  timeout: 30
  retry:
    max_attempts: 3
    backoff: 2               # 指数退避基数

# ===== Mem0 配置 =====
mem0:
  mode: "cloud"              # cloud | self-hosted
  user_id: "default_user"
  cloud:
    api_key: "${MEM0_API_KEY}"
  self_hosted:
    base_url: "http://localhost:8000"

# ===== LLM 配置 =====
llm:
  provider: "gemini"         # gemini | anthropic | openai
  batch_size: 10             # 批量处理大小
  
  gemini:
    model: "gemini-1.5-flash"
    api_key: "${GEMINI_API_KEY}"
    
  anthropic:
    model: "claude-3-5-haiku-20241022"
    api_key: "${ANTHROPIC_API_KEY}"

# ===== 存储配置 =====
storage:
  checkpoint_file: "data/checkpoint.json"
  metrics_file: "data/metrics.json"

# ===== 日志配置 =====
logging:
  level: "INFO"              # DEBUG | INFO | WARNING | ERROR
  file: "logs/memory-janitor.log"
  max_size: "10MB"
  backup_count: 5

# ===== Gradio 配置 =====
gradio:
  port: 7860
  host: "127.0.0.1"
  share: false
```

### 7.2 提示词配置

```
config/prompts/cleaner.txt
┌─────────────────────────────────────────────────────────────────────────────┐
│ 你是一个信息过滤专家。请分析用户的屏幕活动记录，判断是否包含有价值的信息。    │
│                                                                             │
│ 有价值的信息包括：                                                           │
│ - 技术决策和讨论                                                             │
│ - 代码实现思路                                                               │
│ - 问题解决方案                                                               │
│ - 学习笔记和发现                                                             │
│ - 项目进展和里程碑                                                           │
│                                                                             │
│ 无价值的信息包括：                                                           │
│ - 广告和推广内容                                                             │
│ - 社交媒体闲聊                                                               │
│ - 临时搜索（如天气、导航）                                                    │
│ - 重复或冗余的内容                                                           │
│ - 无意义的 UI 元素文本                                                       │
│                                                                             │
│ 请以 JSON 格式返回分析结果。                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

config/prompts/reasoner.txt
┌─────────────────────────────────────────────────────────────────────────────┐
│ 你是一个知识管理专家。请分析以下信息，提取核心事实并进行分类。                 │
│                                                                             │
│ 分类标准：                                                                   │
│ - decision: 核心决策（如技术选型、架构决定）                                  │
│ - discovery: 技术发现（如 bug、性能问题、新特性）                             │
│ - preference: 用户偏好（如编码风格、工具选择）                                │
│ - milestone: 项目里程碑（如版本发布、功能完成）                               │
│ - other: 其他有价值信息                                                      │
│                                                                             │
│ 优先级标准：                                                                 │
│ - high: decision, discovery, preference, milestone 类别                     │
│ - low: other 类别                                                           │
│                                                                             │
│ 请将信息原子化为简短、独立的事实陈述。                                        │
│ 尝试识别关联的项目名称和文件路径。                                            │
│                                                                             │
│ 请以 JSON 格式返回结果。                                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 环境变量

```bash
# .env (不提交到版本控制)

# Mem0
MEM0_API_KEY=your_mem0_api_key

# LLM
GEMINI_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

---

## 8. 监控与可观测性设计

### 8.1 Gradio UI 设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Memory Janitor Agent - 监控面板                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          状态概览                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │ 运行状态  │  │ 上次运行  │  │ 下次运行  │  │ 队列长度  │            │   │
│  │  │  ● 运行中 │  │ 5分钟前   │  │ 55分钟后  │  │    0     │            │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────┐  ┌──────────────────────────────────┐   │
│  │        统计数据               │  │         处理趋势                  │   │
│  │  今日处理: 156 条             │  │  ┌─────────────────────────┐    │   │
│  │  今日存储: 78 条              │  │  │     📊 每小时处理量      │    │   │
│  │  今日丢弃: 78 条              │  │  │  ▁▂▃▅▇█▆▄▃▂▁▂▃▄▅      │    │   │
│  │  存储率: 50%                  │  │  └─────────────────────────┘    │   │
│  └──────────────────────────────┘  └──────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       最近处理记录                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ 时间       │ 内容摘要              │ 状态   │ 节点耗时        │   │   │
│  │  ├─────────────────────────────────────────────────────────────┤   │   │
│  │  │ 14:30:05  │ 决定使用 Redis...     │ ✅ 存储 │ C:0.1s D:0.3s │   │   │
│  │  │ 14:30:04  │ 广告内容...           │ ❌ 丢弃 │ C:0.1s        │   │   │
│  │  │ 14:30:03  │ 发现内存泄露问题...    │ ✅ 存储 │ C:0.1s D:0.2s │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         实时日志                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │ [14:30:05] INFO  Writer: 成功写入 memory_id=xxx              │   │   │
│  │  │ [14:30:04] INFO  Cleaner: 过滤 1 条无价值内容                 │   │   │
│  │  │ [14:30:03] INFO  Collector: 获取 3 条新数据                   │   │   │
│  │  │ [14:30:00] INFO  Trigger: 开始执行定时任务                    │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌────────────────┐                                                        │
│  │  🔄 手动触发    │                                                        │
│  └────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 指标设计

```
metrics.json
┌─────────────────────────────────────────┐
│ {                                       │
│   "daily": {                            │
│     "2026-01-05": {                     │
│       "total_processed": 156,           │
│       "total_stored": 78,               │
│       "total_discarded": 78,            │
│       "total_updated": 5,               │
│       "by_hour": {                       │
│         "14": {"processed": 12, "stored": 6}, │
│         "13": {"processed": 15, "stored": 8}, │
│         ...                             │
│       },                                │
│       "by_category": {                  │
│         "decision": 10,                 │
│         "discovery": 25,                │
│         "preference": 8,                │
│         "milestone": 5,                 │
│         "other": 30                     │
│       },                                │
│       "avg_latency_ms": {               │
│         "collector": 150,               │
│         "cleaner": 800,                 │
│         "deduplicator": 300,            │
│         "reasoner": 600,                │
│         "writer": 200                   │
│       }                                 │
│     }                                   │
│   },                                    │
│   "lifetime": {                         │
│     "total_processed": 12345,           │
│     "total_stored": 6789,               │
│     "first_run": "2026-01-01T00:00:00Z" │
│   }                                     │
│ }                                       │
└─────────────────────────────────────────┘
```

### 8.3 日志设计

```
日志格式:
[{timestamp}] {level} {module}: {message}

示例:
[2026-01-05 14:30:00] INFO  Trigger: 开始执行定时任务 batch_id=batch_20260105_143000
[2026-01-05 14:30:01] INFO  Collector: 获取 15 条新数据 (since=2026-01-05T13:30:00Z)
[2026-01-05 14:30:02] INFO  Cleaner: 处理完成 input=15 output=10 discarded=5
[2026-01-05 14:30:03] INFO  Deduplicator: 处理完成 input=10 add=8 update=1 skip=1
[2026-01-05 14:30:04] INFO  Reasoner: 处理完成 high=3 low=6
[2026-01-05 14:30:05] INFO  Writer: 写入完成 stored=8 updated=1
[2026-01-05 14:30:05] INFO  Trigger: 任务完成 duration=5.2s

日志级别:
├── DEBUG: 详细调试信息（LLM 输入输出、API 响应）
├── INFO: 正常操作信息
├── WARNING: 可恢复的问题（如单条处理失败）
└── ERROR: 严重错误（如 API 不可用）
```

---

## 9. 错误处理与容错设计

### 9.1 错误分类

| 类型 | 示例 | 处理策略 |
|------|------|----------|
| 可恢复 | 单条数据格式错误 | 跳过该条，继续处理 |
| 可恢复 | LLM API 临时超时 | 重试 3 次后跳过 |
| 可恢复 | Mem0 写入失败 | 重试 3 次后记录失败 |
| 不可恢复 | Pieces OS 不可用 | 终止本次任务，等待下次触发 |
| 不可恢复 | 配置文件缺失 | 启动失败，提示用户 |

### 9.2 重试策略

```
重试配置:
├── max_attempts: 3
├── backoff_base: 2 (秒)
├── backoff_max: 30 (秒)
└── jitter: true (随机抖动)

重试间隔: 2s → 4s → 8s (指数退避)
```

### 9.3 降级策略

```
场景: LLM API 不可用

降级方案:
├── 方案 A: 切换到备用 LLM 提供商
├── 方案 B: 使用简化规则（正则匹配）替代 LLM 降噪
└── 方案 C: 跳过 Cleaner/Reasoner，直接存储原始数据

当前选择: 方案 A（配置多个 LLM 提供商）
```

### 9.4 数据一致性

```
Checkpoint 更新时机:
├── Collector 成功后 → 更新 last_sync_time
├── 整批完成后 → 更新 stats
└── 失败时 → 不更新（支持重试）

原子性保证:
├── 使用临时文件写入，成功后原子重命名
└── 保留上一次 checkpoint 备份
```

---

## 10. 部署方案

### 10.1 本地部署架构

```
macOS 本地环境
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   Pieces OS     │     │ Memory Janitor  │     │   Gradio UI     │       │
│  │   (已安装)      │ ←── │   (Python)      │ ──→ │  (localhost:    │       │
│  │   :1000        │     │                 │     │   7860)         │       │
│  └─────────────────┘     └────────┬────────┘     └─────────────────┘       │
│                                   │                                         │
│                                   ▼                                         │
│                          ┌─────────────────┐                               │
│                          │   本地文件系统   │                               │
│                          │  - checkpoint   │                               │
│                          │  - metrics      │                               │
│                          │  - logs         │                               │
│                          └─────────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              云端服务                                        │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐                               │
│  │   Mem0 Cloud    │     │  Gemini/Claude  │                               │
│  │   (或本地)      │     │     API         │                               │
│  └─────────────────┘     └─────────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 启动方式

```bash
# 方式 1: 直接运行（前台）
python -m src.main

# 方式 2: 后台运行
nohup python -m src.main &

# 方式 3: 使用 launchd (macOS 服务)
# 创建 ~/Library/LaunchAgents/com.memory-janitor.plist

# 方式 4: 仅启动 Gradio UI（调试用）
python -m src.ui.gradio_app
```

### 10.3 依赖管理

```
requirements.txt
├── langgraph>=0.2.0
├── langchain-core>=0.3.0
├── mem0ai>=0.1.0
├── google-generativeai>=0.8.0
├── anthropic>=0.40.0
├── gradio>=5.0.0
├── apscheduler>=3.10.0
├── pyyaml>=6.0
├── python-dotenv>=1.0.0
├── httpx>=0.27.0
└── pydantic>=2.0.0

# Pieces OS SDK (待确认)
# pieces-os-client>=x.x.x
```

### 10.4 目录结构（运行时）

```
pieces-to-mem0/
├── src/                    # 源代码
├── config/
│   ├── config.yaml         # 主配置
│   └── prompts/            # 提示词
├── data/
│   ├── checkpoint.json     # 同步状态
│   └── metrics.json        # 统计指标
├── logs/
│   └── memory-janitor.log  # 日志文件
├── .env                    # 环境变量（不提交）
├── requirements.txt
└── pyproject.toml
```

---

## 11. 技术风险与缓解

### 11.1 风险矩阵

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Pieces OS API 能力不足 | 中 | 高 | 提前调研，准备降级方案 |
| LLM 蒸馏质量不稳定 | 中 | 中 | 迭代优化提示词，增加人工反馈 |
| LLM API 成本过高 | 低 | 中 | 使用低成本模型，批量处理 |
| Mem0 查重性能瓶颈 | 低 | 中 | 本地缓存，限制 search 范围 |
| 后台进程被系统杀死 | 低 | 低 | 使用 launchd 管理，自动重启 |

### 11.2 Pieces OS 调研计划

```
调研任务:
1. 安装 Pieces OS SDK
2. 确认可用 API 端点
3. 测试数据获取能力
4. 确认增量查询支持
5. 测试 Webhook 支持（如有）

预计耗时: 0.5-1 天

降级方案（如 API 不足）:
├── 使用文件系统监控替代
├── 定期导出 Pieces 数据手动导入
└── 联系 Pieces 团队寻求支持
```

---

## 12. 实施路线图

### 12.1 阶段划分

```
Phase 1: 基础框架 (3-4 天)
├── 项目结构搭建
├── 配置管理实现
├── LangGraph 基础工作流
├── State 定义
└── 日志系统

Phase 2: 外部集成 (3-4 天)
├── Pieces OS API 调研与集成
├── Mem0 Client 实现
├── LLM Client 实现（多提供商）
└── 单元测试

Phase 3: 核心节点 (4-5 天)
├── Collector 节点
├── Cleaner 节点
├── Deduplicator 节点
├── Reasoner 节点
├── Writer 节点
└── 集成测试

Phase 4: 调度与监控 (2-3 天)
├── Trigger Manager
├── Checkpoint 管理
├── Gradio UI
└── 指标收集

Phase 5: 优化与文档 (2-3 天)
├── 提示词优化
├── 性能调优
├── 错误处理完善
└── 用户文档

总计: 14-19 天
```

### 12.2 里程碑

| 里程碑 | 目标 | 预计完成 |
|--------|------|----------|
| M1 | Pieces API 调研完成 | Day 2 |
| M2 | 基础工作流可运行 | Day 5 |
| M3 | 端到端数据流通 | Day 10 |
| M4 | Gradio 监控可用 | Day 14 |
| M5 | 生产就绪 | Day 17 |

### 12.3 验收检查点

```
M2 验收:
├── [ ] LangGraph 工作流可执行
├── [ ] 配置文件可加载
├── [ ] 日志正常输出

M3 验收:
├── [ ] Pieces 数据可获取
├── [ ] LLM 降噪正常工作
├── [ ] Mem0 写入成功
├── [ ] Checkpoint 正确更新

M4 验收:
├── [ ] 定时触发正常
├── [ ] 手动触发正常
├── [ ] Gradio UI 展示正确
├── [ ] 统计数据准确

M5 验收:
├── [ ] 后台稳定运行 24 小时
├── [ ] 错误处理正确
├── [ ] 资源占用合理
└── [ ] 用户文档完整
```

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| 蒸馏 (Distillation) | 从原始数据中提取核心信息的过程 |
| 原子化 (Atomization) | 将复杂信息压缩为简短独立的事实 |
| Checkpoint | 记录同步进度的状态文件 |
| 漏斗模型 | 数据逐层过滤，最终存储精华 |

### B. 参考资料

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Mem0 文档](https://docs.mem0.ai/)
- [Pieces OS 文档](https://docs.pieces.app/) (待调研)
- [Gradio 文档](https://www.gradio.app/docs)
- [APScheduler 文档](https://apscheduler.readthedocs.io/)

---

**文档结束**
