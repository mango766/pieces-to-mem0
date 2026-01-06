# <img src="https://raw.githubusercontent.com/mem0ai/mem0/main/docs/images/banner-sm.png" width="80" align="left"> Memory Janitor

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-supported-success?logo=apple)
![Windows](https://img.shields.io/badge/Windows-supported-success?logo=windows)
![Linux](https://img.shields.io/badge/Linux-supported-success?logo=linux&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

简体中文 | [English](./README.en.md)

---

> [!IMPORTANT]
> **前置依赖**：本工具需要 [Pieces OS](https://pieces.app/) 在本地运行（默认端口 39300）。

## 项目简介

**针对 AI 编程助手"记忆孤岛"问题，基于 LangGraph 工作流构建的个人记忆整合 Agent，通过 LLM 驱动的采集-降噪-去重-分类-存储五阶段管道，将 Pieces OS 屏幕活动数据蒸馏为结构化语义记忆，持久化至 Mem0 实现跨工具长期记忆共享。**

---

## 演示

<table align="center">
  <tr>
    <td align="center"><b>🇨🇳 中文界面</b><br><img src="docs/assets/dashboard-zh.png" width="400"></td>
    <td align="center"><b>🇬🇧 English UI</b><br><img src="docs/assets/dashboard-en.png" width="400"></td>
  </tr>
</table>

---

## 功能特性

| 功能 | 描述 |
|------|------|
| 🔄 **自动采集** | 从 Pieces OS 获取屏幕活动、OCR 文本、工作流摘要 |
| 🧹 **智能降噪** | LLM 驱动过滤广告、闲聊等无价值内容 |
| 🔍 **语义去重** | 调用 Mem0 search() 避免重复存储 |
| 🏷️ **优先级分类** | 自动识别核心决策、技术发现、用户偏好、项目里程碑 |
| 💾 **持久存储** | 写入 Mem0，供 Claude Code / Cursor 等工具调用 |
| 📊 **可视化监控** | Gradio Dashboard 中英文双语支持 |
| ⏰ **定时调度** | APScheduler 后台自动运行 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    表现层 (Presentation)                      │
│  Gradio Dashboard │ CLI 命令 │ Webhook (预留)                 │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                 业务层 (LangGraph Workflow)                   │
│  Collector → Cleaner → Deduplicator → Reasoner → Writer      │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    集成层 (Integration)                       │
│  Pieces Client │ LLM (Gemini/Claude) │ Mem0 Client            │
└─────────────────────────────────────────────────────────────┘
```

**5 个处理节点**：
| 节点 | 功能 |
|------|------|
| **Collector** | 从 Pieces OS API 获取增量活动数据 |
| **Cleaner** | LLM 驱动降噪，过滤无价值内容 |
| **Deduplicator** | 语义查重，避免重复存储 |
| **Reasoner** | 分类优先级，提取原子化事实 |
| **Writer** | 写入 Mem0，携带丰富元数据 |

---

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/pieces-to-mem0.git
cd pieces-to-mem0
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入 API 密钥：

```bash
# Mem0 API 密钥 (必需)
MEM0_API_KEY=your_mem0_api_key

# LLM 提供商 (二选一)
GOOGLE_API_KEY=your_gemini_api_key
# 或
ANTHROPIC_API_KEY=your_claude_api_key
```

### 4. 验证安装

```bash
memory-janitor status
```

预期输出：
- 🟢 Pieces OS: 在线 (Port 39300)
- 🟢 Mem0: 在线 (Cloud)
- ✅ 整体状态: 所有服务正常运行

---

## 使用方法

### CLI 命令

```bash
# 运行一次处理
memory-janitor run

# 作为后台守护进程运行
memory-janitor daemon

# 启动 Gradio 监控面板
memory-janitor dashboard

# 检查服务状态
memory-janitor status
```

### 快速启动

```bash
./run.sh
```

---

## 配置详解

配置文件位于 `config/settings.yaml`：

### `app` - 应用配置
- **`name`**
  - **默认值**: `memory-janitor`
  - **描述**: 应用名称
- **`version`**
  - **默认值**: `0.1.0`
  - **描述**: 应用版本号
- **`debug`**
  - **默认值**: `false`
  - **描述**: 是否启用调试模式
  - **可选值**: `true` / `false`

### `pieces` - Pieces OS 配置
- **`host`**
  - **默认值**: `localhost`
  - **描述**: Pieces OS 主机地址
- **`port`**
  - **默认值**: `39300`
  - **描述**: Pieces OS 端口号
- **`timeout`**
  - **默认值**: `30`
  - **描述**: API 请求超时时间（秒）
- **`checkpoint_file`**
  - **默认值**: `.pieces_checkpoint.json`
  - **描述**: 增量同步检查点文件路径

### `mem0` - Mem0 配置
- **`mode`**
  - **默认值**: `cloud`
  - **描述**: Mem0 运行模式
  - **可选值**: `cloud` / `local`
- **`api_base`**
  - **默认值**: `https://api.mem0.ai`
  - **描述**: Mem0 API 地址（local 模式下需修改）
- **`user_id`**
  - **默认值**: `default_user`
  - **描述**: Mem0 用户标识

### `llm` - LLM 配置
- **`provider`**
  - **默认值**: `gemini`
  - **描述**: LLM 提供商
  - **可选值**: `gemini` / `anthropic`
- **`model`**
  - **默认值**: `gemini-2.0-flash-exp`
  - **描述**: 模型名称
- **`temperature`**
  - **默认值**: `0.3`
  - **描述**: 生成温度（0-1）
- **`max_tokens`**
  - **默认值**: `4096`
  - **描述**: 最大输出 token 数

### `scheduler` - 调度器配置
- **`enabled`**
  - **默认值**: `true`
  - **描述**: 是否启用定时任务
  - **可选值**: `true` / `false`
- **`interval_minutes`**
  - **默认值**: `30`
  - **描述**: 执行间隔（分钟）
- **`timezone`**
  - **默认值**: `Asia/Shanghai`
  - **描述**: 时区设置

### `pipeline` - 处理管道配置
- **`batch_size`**
  - **默认值**: `50`
  - **描述**: 每批处理的活动数量
- **`dedup_threshold`**
  - **默认值**: `0.85`
  - **描述**: 去重相似度阈值（0-1）
- **`cleaner_prompt`**
  - **默认值**: `prompts/cleaner.txt`
  - **描述**: 清洗器提示词文件路径
- **`reasoner_prompt`**
  - **默认值**: `prompts/reasoner.txt`
  - **描述**: 推理器提示词文件路径

### `dashboard` - 监控面板配置
- **`host`**
  - **默认值**: `127.0.0.1`
  - **描述**: Dashboard 监听地址
- **`port`**
  - **默认值**: `7860`
  - **描述**: Dashboard 端口号
- **`share`**
  - **默认值**: `false`
  - **描述**: 是否生成公开分享链接
  - **可选值**: `true` / `false`

### `logging` - 日志配置
- **`level`**
  - **默认值**: `INFO`
  - **描述**: 日志级别
  - **可选值**: `DEBUG` / `INFO` / `WARNING` / `ERROR`
- **`format`**
  - **默认值**: `json`
  - **描述**: 日志格式
  - **可选值**: `json` / `console`
- **`file`**
  - **默认值**: `logs/memory-janitor.log`
  - **描述**: 日志文件路径
- **`rotation`**
  - **默认值**: `10MB`
  - **描述**: 日志轮转大小

---

## 优先级分类

系统自动将记忆分为 5 个优先级类别：

| 类别 | 标识 | 描述 |
|------|------|------|
| 🔴 核心决策 | `core_decision` | 架构决策、技术选型、重要结论 |
| 🟠 技术发现 | `tech_discovery` | 新学到的技术知识、解决方案 |
| 🟡 用户偏好 | `user_preference` | 个人习惯、工具偏好、工作流程 |
| 🟢 项目里程碑 | `project_milestone` | 功能完成、版本发布、重要进展 |
| ⚪ 一般信息 | `general_info` | 其他有价值但非关键的信息 |

---

## 问题排查

### 提交 Issue 前请准备

1. **导出日志**：
   ```bash
   cat logs/memory-janitor.log | tail -100
   ```

2. **检查服务状态**：
   ```bash
   memory-janitor status
   ```

3. **截图 Dashboard 状态面板**

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 🔴 Pieces OS 离线 | 确保 Pieces 应用已启动，检查端口 39300 |
| 🔴 Mem0 连接失败 | 检查 `MEM0_API_KEY` 是否正确配置 |
| 🔴 LLM 调用失败 | 检查 `GOOGLE_API_KEY` 或 `ANTHROPIC_API_KEY` |
| 🟡 处理缓慢 | 调整 `pipeline.batch_size` 或升级 LLM 模型 |

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码格式化
ruff format .

# 类型检查
mypy src/
```

---

## 许可证

MIT License

---

## 致谢

- [Pieces](https://pieces.app/) - 智能代码片段管理
- [Mem0](https://mem0.ai/) - AI 记忆层
- [LangGraph](https://github.com/langchain-ai/langgraph) - 工作流编排
- [Gradio](https://gradio.app/) - 快速 UI 构建
