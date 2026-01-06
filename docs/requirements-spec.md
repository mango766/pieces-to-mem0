# 需求规格书 (SRS)：个人记忆巩固智能体 (Memory Janitor Agent)

> **版本**: 1.0  
> **日期**: 2026-01-05  
> **状态**: 已确认

---

## 1. 项目概述

### 1.1 项目名称
Memory Janitor Agent（个人记忆巩固智能体）

### 1.2 项目定义
一个基于 **LangGraph** 运行的异步后台智能体，负责连接感知端 (Pieces OS) 与记忆端 (Mem0)，实现数据的无感采集、智能蒸馏与精准存储。

### 1.3 核心价值
将 Pieces OS 捕获的"视觉原始数据"通过漏斗模型蒸馏为 Mem0 的"语义核心记忆"，使用户在使用 Claude Code/Cursor 等工具时能够调取个人长期记忆。

### 1.4 目标用户
- 个人开发者
- 知识工作者
- 需要跨工具记忆同步的用户

---

## 2. 系统架构

### 2.1 总体架构（异步解耦架构）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          用户工作流（日常操作）                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    感知层 (Sensory Layer - Pieces OS)                    │
│         全量、无感捕捉屏幕视觉信息、OCR 文本及应用上下文                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │ API 调用
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     蒸馏层 (Agent - LangGraph)                           │
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌────────────┐  │
│  │Collector │ → │ Cleaner  │ → │ Deduplicator │ → │ Reasoner │ → │Mem0 Writer │  │
│  │ 数据采集  │   │ 清洗降噪  │   │   查重去重    │   │ 优先级判断 │   │  记忆写入   │  │
│  └──────────┘   └──────────┘   └──────────────┘   └──────────┘   └────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │ SDK 调用
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    存储层 (Memory Layer - Mem0)                          │
│              存放结构化、原子化的长期事实（支持本地/云端）                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │ MCP (Mem0 原生)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    查询层 (Interface Layer)                              │
│              Claude Code / Cursor 通过 Mem0 MCP 调取记忆                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 LangGraph 节点设计

| 节点 | 名称 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| 1 | Collector | 通过 API 接入 Pieces，获取增量原始数据 | 触发信号 + checkpoint | raw_items |
| 2 | Cleaner | 清洗降噪，剔除无价值信息 | raw_items | cleaned_items |
| 3 | Deduplicator | 调用 Mem0 API 查重，避免重复存储 | cleaned_items | deduplicated_items |
| 4 | Reasoner | 判断优先级，决定存储或丢弃 | deduplicated_items | prioritized_items |
| 5 | Mem0 Writer | 最终写入 Mem0 | prioritized_items | stored_count |

### 2.3 State 设计

```python
from typing import TypedDict

class MemoryJanitorState(TypedDict):
    # 原始数据
    raw_items: list[dict]          # Pieces 原始数据
    
    # 处理中间态
    cleaned_items: list[dict]      # 清洗后的数据
    deduplicated_items: list[dict] # 去重后的数据
    prioritized_items: list[dict]  # 带优先级标记的数据
    
    # 结果
    stored_count: int              # 成功存储数量
    discarded_count: int           # 丢弃数量
    
    # 元数据
    batch_id: str                  # 批次 ID
    timestamp: str                 # 处理时间
```

---

## 3. 功能需求

### 3.1 数据采集 (Collector 节点)

#### FR-3.1.1 Pieces OS API 集成
- **描述**: 通过 Pieces OS SDK 调用本地 API 获取数据
- **数据类型**:
  - Workstream Summaries（工作流摘要）
  - OCR Text（截屏识别文本）
  - Associated Metadata（应用名称、网页标题、文档路径）
- **来源**: Q3, Q3.1

#### FR-3.1.2 增量数据获取
- **描述**: 仅获取上次处理后的新增数据
- **实现**: 记录 checkpoint（上次处理时间戳），每次获取该时间点之后的数据
- **来源**: Q20

#### FR-3.1.3 混合触发模式
- **描述**: 支持多种触发方式
- **触发方式**:
  | 方式 | 说明 | 配置项 |
  |------|------|--------|
  | 定时触发 | 每小时自动执行 | `trigger.interval: 3600` |
  | 手动触发 | 用户主动调用 | CLI 命令或 Gradio 按钮 |
  | Webhook（待调研） | Pieces OS 事件驱动 | 需确认 Pieces 支持情况 |
- **来源**: Q4, Q4.1

### 3.2 清洗降噪 (Cleaner 节点)

#### FR-3.2.1 LLM 驱动降噪
- **描述**: 使用 LLM 识别并剔除无价值信息
- **过滤目标**:
  - 广告内容
  - 社交媒体闲聊
  - 临时搜索记录
  - 重复/冗余信息
- **实现**: 通过系统提示词定义过滤规则，提示词存放在配置文件中
- **来源**: Q7, Q7.1

#### FR-3.2.2 可配置 LLM
- **描述**: 支持多种 LLM 切换
- **支持的 LLM**:
  - Gemini 1.5 Flash
  - Claude 3.5 Haiku
  - 其他兼容 OpenAI API 的模型
- **配置方式**: YAML 配置文件
- **来源**: Q2

### 3.3 查重去重 (Deduplicator 节点)

#### FR-3.3.1 Mem0 查重
- **描述**: 写入前执行 search，检测是否存在相似记忆
- **策略**（待设计）:
  - 语义相似度匹配
  - LLM 判断是否矛盾/更新
  - 精确匹配作为辅助
- **来源**: Q9

#### FR-3.3.2 冲突处理
- **描述**: 发现新信息与旧记忆矛盾时，执行 update 而非重复添加
- **来源**: 原始需求文档

### 3.4 优先级判断 (Reasoner 节点)

#### FR-3.4.1 高价值内容识别
- **描述**: 识别并标记高优先级内容
- **高优先级类别**:
  | 类别 | 示例 |
  |------|------|
  | 核心决策 | "决定改用 Redis 作为缓存" |
  | 技术发现 | "发现某库在 Windows 环境下有内存泄露" |
  | 用户偏好 | "用户更喜欢使用函数式编程风格" |
  | 项目里程碑 | "Alpha 版本接口文档已初步完成" |
- **来源**: Q21, 原始需求文档

#### FR-3.4.2 优先级分级
- **描述**: 非高优先级内容标记为低优先级，仍可保留
- **处理逻辑**:
  - 高优先级 → 进入存储节点
  - 低优先级 → 进入存储节点（带低优先级标记）
  - 废话/无价值 → 丢弃，记录 discarded_count
- **来源**: Q21

### 3.5 记忆写入 (Mem0 Writer 节点)

#### FR-3.5.1 Mem0 SDK 调用
- **描述**: 直接调用 Mem0 Python SDK 的 `add()` 接口
- **部署支持**: 
  - Mem0 Cloud（托管服务）
  - 本地自托管 Mem0 Server
- **配置方式**: YAML 配置文件切换
- **来源**: Q5

#### FR-3.5.2 元数据标记
- **描述**: 每条记忆携带丰富的元数据
- **元数据字段**:
  | 字段 | 类型 | 说明 |
  |------|------|------|
  | source_type | string | "screenshot_ocr" / "browser_activity" / ... |
  | timestamp | datetime | 原始捕捉时间 |
  | project | string | 智能体识别出的关联项目名 |
  | priority | string | "high" / "low" |
  | category | string | "decision" / "discovery" / "preference" / "milestone" / "other" |
  | confidence | float | LLM 判断的置信度 (0-1) |
  | related_files | list[string] | 关联的文件路径 |
- **来源**: Q22, 原始需求文档

#### FR-3.5.3 事实原子化
- **描述**: 将复杂的活动流压缩为简短、独立的 Fact 字符串
- **来源**: 原始需求文档

### 3.6 监控界面

#### FR-3.6.1 Gradio 监控页面
- **描述**: 使用 Gradio 构建监控界面
- **展示内容**:
  - 任务队列长度
  - 最近处理的记录
  - 成功/失败计数
  - 每条记录的处理流程（经过哪些节点、耗时）
  - 实时日志流
  - 统计图表（每小时处理量、蒸馏通过率）
- **来源**: Q17, Q18

#### FR-3.6.2 手动触发
- **描述**: 通过 Gradio 界面手动触发蒸馏任务
- **来源**: Q4

---

## 4. 技术需求

### 4.1 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 框架 | LangGraph | 节点式工作流编排 |
| 语言 | Python | LangGraph 原生支持 |
| 感知端 | Pieces OS SDK | 本地 API 调用 |
| 存储端 | Mem0 Python SDK | 支持 Cloud/Self-hosted |
| LLM | Gemini 1.5 Flash / Claude 3.5 Haiku | 可配置切换 |
| 监控 | Gradio | 轻量级 Web UI |
| 配置 | YAML/TOML | 配置文件管理 |

### 4.2 项目结构（建议）

```
pieces-to-mem0/
├── src/
│   ├── __init__.py
│   ├── main.py                 # 入口
│   ├── graph.py                # LangGraph 定义
│   ├── state.py                # State 类型定义
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── collector.py        # 节点 1: 数据采集
│   │   ├── cleaner.py          # 节点 2: 清洗降噪
│   │   ├── deduplicator.py     # 节点 3: 查重去重
│   │   ├── reasoner.py         # 节点 4: 优先级判断
│   │   └── writer.py           # 节点 5: Mem0 写入
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── pieces_client.py    # Pieces OS API 封装
│   │   ├── mem0_client.py      # Mem0 SDK 封装
│   │   └── llm_client.py       # LLM 调用封装
│   ├── ui/
│   │   └── gradio_app.py       # Gradio 监控界面
│   └── utils/
│       ├── __init__.py
│       ├── config.py           # 配置加载
│       ├── checkpoint.py       # Checkpoint 管理
│       └── logger.py           # 日志工具
├── config/
│   ├── config.yaml             # 主配置文件
│   └── prompts/
│       ├── cleaner.txt         # 清洗降噪提示词
│       └── reasoner.txt        # 优先级判断提示词
├── tests/
│   └── ...
├── requirements.txt
└── pyproject.toml
```

### 4.3 配置文件设计

```yaml
# config/config.yaml

# 触发配置
trigger:
  mode: "scheduled"  # scheduled | manual | webhook
  interval: 3600     # 定时触发间隔（秒）

# Pieces OS 配置
pieces:
  base_url: "http://localhost:1000"
  timeout: 30

# Mem0 配置
mem0:
  mode: "cloud"  # cloud | self-hosted
  cloud:
    api_key: "${MEM0_API_KEY}"
  self_hosted:
    base_url: "http://localhost:8000"
  user_id: "default_user"

# LLM 配置
llm:
  provider: "gemini"  # gemini | anthropic | openai
  gemini:
    model: "gemini-1.5-flash"
    api_key: "${GEMINI_API_KEY}"
  anthropic:
    model: "claude-3-5-haiku-20241022"
    api_key: "${ANTHROPIC_API_KEY}"

# 日志配置
logging:
  level: "INFO"
  file: "logs/memory-janitor.log"

# Gradio 配置
gradio:
  port: 7860
  share: false
```

### 4.4 Pieces OS API 调研（待完成）

> ⚠️ **待调研事项**:
> 1. Pieces OS 是否支持 Webhook 事件通知
> 2. 可用的 API 端点及数据格式
> 3. 增量数据获取的最佳方式

---

## 5. 非功能需求

### 5.1 资源占用
- **优先级**: 高
- **要求**: 低资源占用，后台静默运行
- **当前约束**: 无硬性限制，越低越好
- **来源**: Q10, Q10.1

### 5.2 部署环境
- **目标环境**: 本地 macOS（与 Pieces OS 同机）
- **来源**: Q11

### 5.3 错误处理
- **策略**: 静默失败，记录日志，继续处理下一条
- **来源**: Q16

### 5.4 日志
- **格式**: 文件日志，可配置级别
- **来源**: Q15

---

## 6. 约束条件

### 6.1 技术约束
- 必须使用 LangGraph 框架
- 必须兼容 Pieces OS 本地 API
- 必须兼容 Mem0 Python SDK

### 6.2 环境约束
- 运行于 macOS 本地环境
- 与 Pieces OS 同机运行

### 6.3 依赖约束
- Pieces OS 需已安装并运行
- Mem0 服务需可访问（Cloud 或 Self-hosted）
- LLM API 需可访问

---

## 7. 验收标准

### 7.1 功能验收
| 功能 | 验收条件 |
|------|----------|
| 数据采集 | 能够从 Pieces OS 获取增量数据 |
| 清洗降噪 | 能够过滤广告、闲聊等无价值内容 |
| 查重去重 | 不会重复存储相同/相似记忆 |
| 优先级判断 | 能够识别四类高价值内容并正确标记 |
| 记忆写入 | 成功写入 Mem0 并携带完整元数据 |
| 监控界面 | Gradio 页面正常展示任务状态 |
| 混合触发 | 支持定时和手动两种触发方式 |

### 7.2 非功能验收
| 指标 | 验收条件 |
|------|----------|
| 后台运行 | 不影响用户日常工作 |
| 错误恢复 | 单条处理失败不影响整体流程 |

---

## 8. 待澄清事项

| 编号 | 事项 | 重要性 | 状态 |
|------|------|--------|------|
| 1 | Pieces OS Webhook 支持情况 | 中 | 待调研 |
| 2 | Pieces OS API 具体端点和数据格式 | 高 | 待调研 |
| 3 | 冲突检测的具体策略设计 | 高 | 待设计 |
| 4 | 蒸馏准确率/误报率的具体指标 | 低 | 待定 |

---

## 9. 风险与假设

### 9.1 假设
1. Pieces OS 提供足够的 API 能力获取所需数据
2. Mem0 SDK 满足所有存储需求
3. 用户已配置好 LLM API 访问

### 9.2 风险
| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Pieces OS API 能力不足 | 无法获取所需数据 | 提前调研，必要时联系 Pieces 团队 |
| LLM 调用成本过高 | 运行成本增加 | 使用轻量模型，优化调用频率 |
| 蒸馏准确率不达预期 | 存储无价值信息或丢失有价值信息 | 迭代优化提示词，增加人工反馈机制 |

---

## 10. 问答记录

| 问题 | 回答 |
|------|------|
| Q1. 技术栈选择 | LangGraph（已更正） |
| Q2. LLM 选择策略 | C) 可配置，支持多种 LLM 切换 |
| Q3. Pieces OS 集成方式 | C) 不确定，需要调研 |
| Q3.1 Pieces OS API 调研 | A) 请调研 Pieces OS SDK/API 文档 |
| Q4. 触发时机与频率 | D) 混合模式 |
| Q4.1 定时批量处理频率 | D) 每小时 |
| Q5. Mem0 部署方式 | C) 两者都支持，可配置 |
| Q6. MCP Server 实现 | 不涉及，直接使用 Mem0 MCP |
| Q7. 降噪规则可配置性 | D) 基于 LLM 系统提示词实现 |
| Q7.1 LLM 系统提示词管理 | B) 存放在配置文件中 |
| Q8. 项目/上下文识别 | E) 以上组合 |
| Q9. 冲突检测策略 | D) 需要设计具体策略 |
| Q10. 非功能需求优先级 | 低资源占用最高 |
| Q10.1 资源占用约束 | 目前不限制 |
| Q11. 部署环境 | A) 本地 macOS |
| Q12. 验收标准 | 不涉及 MCP，其他待定 |
| Q14. 配置管理方式 | B) YAML/TOML 配置文件 |
| Q15. 日志与可观测性 | Gradio 前端页面展示任务运行情况 |
| Q16. 错误处理策略 | A) 静默失败，记录日志，继续处理 |
| Q17. 前端监控页面技术栈 | C) Gradio |
| Q18. 监控页面展示信息 | E) 以上全部 |
| Q19. LangGraph State 设计 | A) 设计合理 |
| Q20. Pieces OS 数据获取范围 | A) 增量数据（记录 checkpoint） |
| Q21. 优先级判断规则 | B) 四类高优先级，其他低优先级保留 |
| Q22. Mem0 元数据扩展 | E) 以上全部 |

---

## 附录

### A. LangGraph 节点流程图

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Collector  │ ← Pieces OS API
                    └──────┬──────┘
                           │ raw_items
                           ▼
                    ┌─────────────┐
                    │   Cleaner   │ ← LLM (降噪)
                    └──────┬──────┘
                           │ cleaned_items
                           ▼
                    ┌─────────────┐
                    │Deduplicator │ ← Mem0 search()
                    └──────┬──────┘
                           │ deduplicated_items
                           ▼
                    ┌─────────────┐
                    │  Reasoner   │ ← LLM (优先级)
                    └──────┬──────┘
                           │ prioritized_items
                           ▼
                    ┌─────────────┐
                    │ Mem0 Writer │ ← Mem0 add()/update()
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    END      │
                    └─────────────┘
```

### B. 元数据示例

```json
{
  "text": "决定将缓存方案从 Memcached 迁移到 Redis，因为 Redis 支持更丰富的数据结构",
  "metadata": {
    "source_type": "browser_activity",
    "timestamp": "2026-01-05T14:30:00Z",
    "project": "e-commerce-backend",
    "priority": "high",
    "category": "decision",
    "confidence": 0.92,
    "related_files": [
      "/Users/user/projects/e-commerce/src/cache/redis_client.py"
    ]
  }
}
```

---

**文档结束**
