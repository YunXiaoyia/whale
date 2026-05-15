# Whale V1 平台设计

## 概要

Whale V1 保留现有的命令行用户体验和 `.whale/` 存储布局，同时把运行时收束成更清晰的平台边界。目标不是在当前系统旁边再加一套第二代理系统。目标是把已经存在于 `Whale.ask()`、`ContextManager`、`RunStore`、`tools.py`、provider 客户端、delegation 和 memory 里的能力，正式化为稳定的子系统，这样后续扩展时不会让控制循环更难理解。

V1 应继续兼容以下内容：

- `whale` CLI 和 `python -m whale` 入口。
- 现有的 `WHALE_*` provider 环境变量。
- 现有的 `.whale/sessions/` 和 `.whale/runs/<run_id>/` 目录。
- 现有 run 制品：`task_state.json`、`trace.jsonl` 和 `report.json`。
- 用 `FakeModelClient` 的现有测试，它们在没有真实 provider 的情况下验证行为。

## 当前基线

Whale 已经具备第一版的大部分所需能力：

- 任务运行记录：`RunStore`、`TaskState`、trace 事件、报告、checkpoint。
- 上下文治理：`ContextManager`，包含 section budget、裁剪顺序和 prompt 元数据。
- 工具安全：显式工具注册、路径沙箱、审批模式、密文脱敏、allowlist shell 环境。
- 多 provider 支持：Ollama、OpenAI-compatible、Anthropic-compatible 和 DeepSeek-compatible 客户端。
- Worker 行为：`delegate` 创建一个受边界约束的只读子代理。
- Memory：working memory、文件摘要、episodic notes、durable topics、新鲜度失效和晋升规则。

V1 的主要缺口是：

- 这些能力主要通过构造参数和常量间接配置。
- run 记录没有单一的 schema 合约。
- 工具 policy 和 `Whale.run_tool()` 混在一起。
- provider 配置分散在 CLI 默认值、环境变量和 model client 初始化里。
- delegation 是一个工具实现，而不是 worker 管理子系统。
- skill 发现还不存在。

## 设计原则

- 兼容优先：现有 CLI 命令、本地制品和测试保持有效。
- 默认安全：任何新特性都不应在未显式配置的情况下扩大工具权限。
- 先文本，后执行：V1 里的 skill 是 prompt 指令，不是可执行插件。
- 处处可观测：每个主要子系统都会发出 trace/report 元数据。
- 小接口：先加入稳定的数据契约，再加入高级行为。
- 确定性测试：所有新行为都应能用 fake client 和本地 fixture 测试。

## 运行时和 Run 记录

运行时应继续把 `Whale.ask()` 作为主要公开执行方法，但 V1 会把每次请求视为一次结构化 run。

### 职责

- `SessionStore` 存储可恢复的会话状态。
- `RunStore` 存储一次用户请求的审计制品。
- `TaskState` 存储当前执行状态。
- Checkpoint 存储可恢复性提示和运行时身份。
- Trace 事件存储逐步时间线。
- 报告存储最终摘要和指标。

### V1 合约

Run 制品继续保留在当前位置：

```text
.whale/
  sessions/
    <session_id>.json
  runs/
    <run_id>/
      task_state.json
      trace.jsonl
      report.json
```

每个制品都应该包含或保留 schema version。现有没有 version 的文件应视为 V0 兼容输入。

建议的稳定记录名称：

- `RunRecord`：run id、task id、session id、workspace root、创建时间戳、状态、停止原因、制品路径。
- `TaskRecord`：用户请求、尝试次数、工具步骤、最后一个工具、最终回答、checkpoint id、恢复状态。
- `TraceEvent`：事件名、created_at、payload、脱敏状态。
- `RunReport`：最终 task 状态、prompt 元数据、工具摘要、memory 摘要、worker 摘要、provider 元数据。

### Trace 事件

现有事件应继续有效：

- `run_started`
- `prompt_built`
- `model_requested`
- `model_parsed`
- `tool_executed`
- `checkpoint_created`
- `run_finished`

V1 可以新增这些事件：

- `skill_selected`
- `tool_policy_evaluated`
- `worker_started`
- `worker_finished`
- `memory_promoted`
- `provider_selected`

## 上下文治理

`ContextManager` 应成为正式的上下文 policy 层。它已经会从 prefix、memory、relevant memory、history 和当前请求构造 prompt。

### Sections

V1 保持现有 section 顺序：

```text
prefix
memory
relevant_memory
history
current_request
```

V1 可以在 `prefix` 中加入可选的 skill 内容，或者新增一个放在 `memory` 之前的 `skills` section。为了保持兼容性，默认应把 skill 注入到 `prefix` 中，除非显式启用新的 schema version。

### Policy

上下文 policy 应暴露：

- 总 prompt budget。
- 每个 section 的 budget。
- 每个 section 的 floor。
- 裁剪顺序。
- relevant memory 上限。
- skill 指令 budget。
- 是否启用上下文裁剪。

### 元数据

每次 prompt 构建都应继续报告：

- 每个 section 的原始字符数和渲染字符数。
- 应用的裁剪。
- 选中的相关 memory notes。
- prompt cache key。
- workspace fingerprint。
- 工具签名。

V1 还应增加：

- 选中的 skill 名称和来源。
- context policy 名称。
- budget profile 名称。

## Skill System

Skill 是 V1 中最大的新增子系统。V1 应保持它简单而安全：skill 是本地 markdown 指令文件，不是可执行代码。

### 发现路径

默认发现顺序：

```text
<repo>/skills/
<repo>/.whale/skills/
~/.whale/skills/
```

V1 只加载名为 `SKILL.md` 的文件。允许嵌套的 skill 目录。

### Skill Manifest

每个 skill 在内部都应表示为 `SkillManifest`：

- `name`：稳定的 skill id。
- `description`：简短的用户可读摘要。
- `triggers`：让该 skill 相关的词或短语。
- `source_path`：`SKILL.md` 的绝对路径。
- `scope`：`project` 或 `user`。
- `instructions`：裁剪后的 markdown 内容。
- `enabled`：布尔值。

### 选择

Skill 选择应是确定性的：

- 先匹配显式的 skill 提及，例如 `$python-testing`。
- 再匹配当前用户请求中的 trigger 词。
- 然后在配置了默认项时包含 project-default skills。
- 根据数量和字符 budget 限制已选中的 skills。

### Prompt 注入

选中的 skills 应渲染为简洁指令：

```text
Selected skills:
- <name>: <description>
  Source: <relative path>
  Instructions:
  <clipped body>
```

V1 不应执行 skill 引用的脚本。它只是向模型说明可用的工作流。

### 安全

- 跳过 discovery roots 之外的 skills。
- 裁剪 skill 内容。
- skill 名称必须是简单、适合路径的标识符。
- trace 事件记录 skill 选择，但除非显式配置，否则不记录完整的私有 skill 内容。

## 工具安全 policy

当前工具模型已经是个不错的基础：显式注册、schema 验证、风险标志、审批模式、路径沙箱和环境 allowlist。

V1 应在不改变用户行为的前提下，把 policy 决策和工具执行分离。

### Tool Policy 字段

建议的 `ToolPolicy` 字段：

- `tool_name`
- `risk_level`：`low`、`medium`、`high`
- `approval`：`never`、`ask`、`auto`
- `read_only`
- `allowed_paths`
- `denied_paths`
- `shell_env_allowlist`
- `timeout_limit`
- `max_output_chars`
- `repeat_call_policy`

### 默认 policy

保留当前行为：

- `list_files`、`read_file`、`search` 和 `delegate` 风险较低。
- `run_shell`、`write_file` 和 `patch_file` 风险较高。
- `--approval ask` 在高风险工具前询问。
- `--approval auto` 允许高风险工具。
- `--approval never` 拒绝高风险工具。
- 只读子代理不能运行危险工具。

### 审计

每次工具调用在执行前都应发出一个 `tool_policy_evaluated` 事件，包含：

- 工具名。
- 风险级别。
- 审批决定。
- 安全事件类型。
- 只读状态。
- 已知的话，受影响路径。

现有的 `tool_executed` 元数据仍然作为最终执行结果保留。

## 多 Provider 配置

当前 provider 设置主要在 `cli.py` 和 model client 构造器里。V1 应加入一个 provider profile 层，同时保留所有现有环境变量。

### 现有 Provider

- `ollama`
- `openai`
- `anthropic`
- `deepseek`

### Provider Profile

建议的 `ProviderProfile` 字段：

- `name`
- `client_type`
- `model`
- `base_url`
- `api_key_env`
- `legacy_api_key_envs`
- `timeout`
- `temperature`
- `top_p`
- `supports_prompt_cache`

### 配置来源

优先级保持不变：

```text
CLI args > .env WHALE_* variables > legacy environment variables > defaults
```

V1 以后可以增加可选配置文件，但不应强制要求。

### 兼容性

当前变量仍然有效：

- `WHALE_OPENAI_API_BASE`
- `WHALE_OPENAI_API_KEY`
- `WHALE_OPENAI_MODEL`
- `WHALE_ANTHROPIC_API_BASE`
- `WHALE_ANTHROPIC_API_KEY`
- `WHALE_ANTHROPIC_MODEL`
- `WHALE_DEEPSEEK_API_BASE`
- `WHALE_DEEPSEEK_API_KEY`
- `WHALE_DEEPSEEK_MODEL`

## Worker 管理

V1 应把 `delegate` 正式化为 worker 管理。此阶段不引入真正的并行执行。

### Worker Model

建议的 `WorkerSpec` 字段：

- `worker_id`
- `parent_run_id`
- `task`
- `read_only`
- `max_steps`
- `allowed_tools`
- `depth`
- `max_depth`
- `workspace_root`

### 行为

V1 的默认行为：

- Worker 是只读的。
- Worker 继承 provider client 和 workspace。
- Worker 共享 run store，但有自己的 task/run state。
- Worker depth 保持有界。
- Worker 结果以文本形式返回给父级。

### Trace 集成

父级 trace 应记录：

- `worker_started`
- `worker_finished`
- Worker run id。
- Worker 状态。
- 裁剪后的 worker 最终回答。

Worker traces 保持在自己的 run 目录中。

## Memory 机制

现有的 `LayeredMemory` 模型将被保留并显式化。

### 层级

- Working memory：当前任务摘要和最近使用的文件。
- File summaries：按规范化工作区路径和 freshness hash 键控的短摘要。
- Episodic notes：来自最近交互的短笔记。
- Durable memory：`.whale/memory/topics/` 下的主题文件。

### Policy

建议的 `MemoryPolicy` 字段：

- Working file limit。
- Episodic note limit。
- File summary limit。
- Relevant memory retrieval limit。
- Durable topic allowlist。
- Promotion patterns。
- Rejection rules。
- 是否启用 freshness invalidation。

### Promotion

V1 保持显式的 durable promotion intent：

- 英文 intent：capture、remember、save、store、persist、note。
- 中文 intent：记住、保存、记录、沉淀、长期记忆、持久记忆。

Promotion 仍然要求结构化 final-answer 行，例如：

```text
Project convention: ...
Decision: ...
Dependency: ...
Preference: ...
```

### 安全

Durable memory 应拒绝：

- Secret-shaped 文本。
- 短期任务状态。
- 冗长且噪声很大的 stdout/stderr/traceback 内容。
- 已脱敏的值。

## 建议的公共接口

这些名称是 V1 实现目标，不需要立即成为 public imports。

```python
class WhaleConfig:
    provider: ProviderProfile
    context: ContextPolicy
    tools: ToolPolicySet
    workers: WorkerPolicy
    memory: MemoryPolicy
    run_store_root: Path
    session_store_root: Path


class ProviderProfile:
    name: str
    model: str
    base_url: str
    timeout: int
    supports_prompt_cache: bool


class ContextPolicy:
    total_budget: int
    section_budgets: dict[str, int]
    section_floors: dict[str, int]
    reduction_order: tuple[str, ...]
    relevant_memory_limit: int


class ToolPolicy:
    tool_name: str
    risk_level: str
    approval: str
    read_only: bool
    timeout_limit: int


class SkillManifest:
    name: str
    description: str
    triggers: tuple[str, ...]
    source_path: Path
    instructions: str


class WorkerSpec:
    worker_id: str
    parent_run_id: str
    task: str
    read_only: bool
    max_steps: int


class MemoryPolicy:
    working_file_limit: int
    episodic_note_limit: int
    file_summary_limit: int
    relevant_memory_limit: int
```

## 实现阶段

### Phase 1: Contracts And Documentation

- 添加这份平台设计文档。
- 为 run/session 文档补充 schema 说明。
- 保持行为不变。

### Phase 2: Configuration Objects

- 引入内部 config dataclass。
- 把构造器常量改成配置默认值。
- 保留所有当前 CLI 参数。

### Phase 3: Skill Discovery

- 添加 skill loader 和确定性 selector。
- 把选中的 skill 文本注入 prompt 元数据和 prefix。
- 为 discovery、selection、clipping 和 trace 元数据添加测试。

### Phase 4: Tool Policy Layer

- 把 `run_tool()` 中的审批/risk 决策抽离出来。
- 添加 `tool_policy_evaluated` trace 事件。
- 保持现有工具执行结果不变。

### Phase 5: Worker Manager

- 用 worker manager 函数包装 `delegate`。
- 添加父子 run 关联。
- 添加 worker trace 汇总事件。

### Phase 6: Run Query And Reports

- 添加只读辅助方法以列出 runs 并加载 run 摘要。
- 扩展报告，加入 provider、skills、worker 和 memory 摘要。

## 验收标准

- 现有测试继续通过。
- `whale --help` 仍然有效。
- 现有 `.env.example` 仍然有效。
- 现有 `.whale/runs/<run_id>/task_state.json`、`trace.jsonl` 和 `report.json` 仍然可读。
- V1 中 skill 不能执行代码。
- Worker 默认只读。
- 工具 policy 决策可追踪。
- provider 选择在 trace/report 元数据中可见。
- memory promotion 仍然是显式的，并且会拒绝 secret-shaped 内容。

## V1 非目标

- 真正的并行 worker 执行。
- 远程 skill 市场。
- 可执行插件。
- 基于数据库的 run 存储。
- CLI flag 的破坏性变更。
- 现有 `.whale/` 状态的迁移要求。
