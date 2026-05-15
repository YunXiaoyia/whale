# Whale

Whale 是一个运行在本地终端里的轻量级 Coding Agent。它面向真实代码仓库工作，可以读取项目结构、搜索代码、执行命令、进行受控文件修改、恢复会话，并为每一次请求生成可审计的本地运行记录。

这个项目不是简单的聊天壳，而是一个小型但完整的 Agent Runtime：模型后端可替换，工具显式注册，高风险动作经过策略校验，Prompt 上下文按预算治理，每次运行都会留下可复盘的本地制品。

## 功能特性

- **本地仓库工作流**：默认在当前目录运行，也可以通过 `--cwd` 指定任意工作区。
- **交互式与一次性任务**：支持 `whale>` 多轮对话，也支持直接传入 prompt 执行单次任务。
- **多模型后端**：支持 Ollama、OpenAI-compatible Responses API、Anthropic-compatible Messages API、DeepSeek-compatible API。
- **受控工具执行**：支持文件列表、文件读取、代码搜索、Shell 命令、文件写入、精确 patch、只读子代理委派。
- **安全策略**：包含路径沙箱、参数校验、审批模式、重复调用拦截、只读 worker、敏感信息脱敏。
- **上下文治理**：Prompt 按 section 组装，支持预算、裁剪顺序和上下文元数据追踪。
- **记忆与恢复**：保存任务摘要、最近文件、文件摘要、临时笔记、持久主题和 checkpoint。
- **运行审计**：每次请求都会在 `.whale/runs/<run_id>/` 下写入 `task_state.json`、`trace.jsonl`、`report.json`。
- **技能指令**：支持发现本地 `SKILL.md`，并仅作为 Prompt 指令注入，不执行技能文件中的脚本。

## 安装

Whale 需要 Python 3.10 或更高版本。推荐使用 Conda 创建独立环境。

创建并激活环境：

```bash
conda create -n whale python=3.10 -y
conda activate whale
```

安装项目：

```bash
python -m pip install -e .
```

安装开发依赖：

```bash
conda install -n whale -c conda-forge pytest ruff -y
```

## 配置

复制环境变量模板，并只填写需要使用的模型后端：

```bash
cp .env.example .env
```

支持的模型后端：

| 模型后端 | 适用场景 | 关键配置 |
| --- | --- | --- |
| `ollama` | 本地 Ollama 模型 | `--host`、`--model` |
| `openai` | OpenAI-compatible Responses API | `WHALE_OPENAI_API_BASE`、`WHALE_OPENAI_API_KEY`、`WHALE_OPENAI_MODEL` |
| `anthropic` | Anthropic-compatible Messages API | `WHALE_ANTHROPIC_API_BASE`、`WHALE_ANTHROPIC_API_KEY`、`WHALE_ANTHROPIC_MODEL` |
| `deepseek` | DeepSeek Anthropic-compatible API | `WHALE_DEEPSEEK_API_BASE`、`WHALE_DEEPSEEK_API_KEY`、`WHALE_DEEPSEEK_MODEL` |

配置优先级：

```text
命令行参数 > .env 中的 WHALE_* 变量 > 旧环境变量 > 默认值
```

不要提交真实 API Key。`.env` 应只保留在本地。

## 快速开始

在当前仓库启动交互式会话：

```bash
conda activate whale
whale --provider deepseek
```

指定其他工作目录：

```bash
conda activate whale
whale --provider deepseek --cwd /path/to/repo
```

执行一次性任务：

```bash
conda run -n whale whale --provider deepseek "检查失败的测试并给出修复方案"
```

使用模块入口：

```bash
conda run -n whale python -m whale --provider openai "总结这个仓库的结构"
```

使用本地 Ollama：

```bash
ollama serve
ollama pull qwen3.5:4b
conda activate whale
whale --provider ollama --model qwen3.5:4b
```

恢复最近一次会话：

```bash
conda activate whale
whale --resume latest
```

注意：`conda run` 适合一次性命令，不适合 `whale>` 这种需要持续读取终端输入的交互模式。交互式使用请先 `conda activate whale`，再直接运行 `whale ...`。

## CLI 参数

查看完整帮助：

```bash
conda run -n whale python -m whale --help
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--cwd` | 工作区目录，默认是当前目录。 |
| `--provider` | 模型后端，可选 `ollama`、`openai`、`anthropic`、`deepseek`。 |
| `--model` | 覆盖默认模型名称。 |
| `--base-url` | OpenAI-compatible、Anthropic-compatible 或 DeepSeek 后端的 API Base URL。 |
| `--resume` | 恢复指定 session id，或使用 `latest` 恢复最近会话。 |
| `--approval` | 高风险工具审批策略：`ask`、`auto`、`never`。 |
| `--secret-env-name` | 额外指定需要在 trace/report 中脱敏的环境变量名。 |
| `--max-steps` | 单次请求允许的最大模型/工具迭代次数。 |
| `--max-new-tokens` | 每次模型输出的最大 token 数。 |

交互式命令：

| 命令 | 说明 |
| --- | --- |
| `/help` | 查看 REPL 内置命令。 |
| `/memory` | 查看当前工作记忆。 |
| `/session` | 查看当前 session 文件路径。 |
| `/reset` | 清空当前 session 的历史和记忆。 |
| `/exit`、`/quit` | 退出 REPL。 |

## 架构设计

Whale 的核心是一个受控 Agent 运行循环：

```text
用户请求
  -> CLI 装配 Agent
  -> 构建工作区快照并注册工具
  -> ContextManager 组装 Prompt
  -> Model Client 返回响应
  -> Runtime 解析最终回答或工具请求
  -> ToolPolicy 校验并审批工具调用
  -> 工具结果写入 history、memory、trace
  -> 循环直到最终回答或触发停止条件
```

核心模块：

| 模块 | 职责 |
| --- | --- |
| `whale/cli.py` | CLI 参数解析、模型后端选择、session 加载、REPL 编排。 |
| `whale/runtime.py` | Agent 主循环、响应解析、工具执行入口、checkpoint、trace、report。 |
| `whale/models.py` | 多模型后端适配层，对上暴露统一 `complete()` 接口。 |
| `whale/tools.py` | 工具注册表和工具实现。 |
| `whale/tool_policy.py` | 工具校验、审批决策、风险元数据和拒绝原因。 |
| `whale/context_manager.py` | Prompt 组装、section budget、上下文裁剪和 prompt 元数据。 |
| `whale/memory.py` | 工作记忆、文件摘要、临时笔记、持久主题和 freshness 检查。 |
| `whale/run_store.py` | run 制品落盘与 run 摘要查询。 |
| `whale/workers.py` | 受限只读 worker、父子 run 关联和 delegate 管理。 |
| `whale/skills.py` | 本地 `SKILL.md` 的安全发现、选择和 prompt 渲染。 |

## 工具模型

Whale 不会动态发现可执行工具。所有工具都必须显式注册，并以结构化说明暴露给模型。

| 工具 | 用途 | 风险级别 |
| --- | --- | --- |
| `list_files` | 列出工作区内文件。 | 低 |
| `read_file` | 按行读取 UTF-8 文件。 | 低 |
| `search` | 使用 `rg` 或降级搜索逻辑搜索代码。 | 低 |
| `run_shell` | 在仓库根目录执行 Shell 命令。 | 高 |
| `write_file` | 在工作区内写入文本文件。 | 高 |
| `patch_file` | 对文件做一次精确文本替换。 | 高 |
| `delegate` | 派发受限只读子代理进行调查。 | 低 |

高风险工具由 `--approval` 控制：

- `ask`：执行前询问。
- `auto`：校验通过后自动执行。
- `never`：拒绝高风险工具。

所有工具调用都会先经过校验。路径必须位于工作区内，参数错误会被拒绝，重复的完全相同工具调用会被拦截，trace 和 report 写入前会进行敏感信息脱敏。

## 运行制品

Whale 将可恢复会话状态和单次请求审计制品分开保存：

```text
.whale/
  sessions/
    <session_id>.json
  runs/
    <run_id>/
      task_state.json
      trace.jsonl
      report.json
  memory/
    MEMORY.md
    topics/
      <topic>.md
```

主要制品：

| 文件 | 作用 |
| --- | --- |
| `sessions/<session_id>.json` | 保存对话历史、记忆状态、checkpoint 和恢复元数据。 |
| `runs/<run_id>/task_state.json` | 保存单次请求的状态机快照。 |
| `runs/<run_id>/trace.jsonl` | 追加写入事件日志，包含 prompt 构建、模型调用、工具策略、工具执行、worker 和结束事件。 |
| `runs/<run_id>/report.json` | 保存最终摘要，包含模型后端、技能、记忆、worker 和工具元数据。 |
| `memory/MEMORY.md` | 持久记忆索引。 |

可以通过 `RunStore` 查询运行摘要：

```python
from whale.run_store import RunStore

store = RunStore(".whale/runs")
runs = store.list_runs(limit=10)
summary = store.load_run_summary(runs[0]["run_id"])
```

制品契约见 `docs/architecture/run-session-schema.md`。

## 技能

Whale 会从以下位置发现只作为 Prompt 指令使用的技能：

```text
<repo>/skills/
<repo>/.whale/skills/
~/.whale/skills/
```

只加载名为 `SKILL.md` 的文件。技能会根据显式 `$skill-name` 提及、触发关键词和默认配置确定性选择，并渲染到 Prompt 中。Whale 不会执行技能文件中引用的脚本。

## 开发

运行测试：

```bash
conda run -n whale python -m pytest -q
```

运行代码检查：

```bash
conda run -n whale ruff check .
```

如果已经激活 `whale` 环境，也可以直接运行：

```bash
python -m pytest -q
ruff check .
```

## 项目状态

Whale V1 已完成本地优先的 Agent Runtime 改造，形成了配置、上下文治理、工具策略、技能、worker、记忆和运行制品等稳定模块边界。当前 V1 交付记录见 `docs/architecture/whale-v1-implementation-status.md`。

## 许可证

当前仓库尚未包含许可证文件。
