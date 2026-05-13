# Whale V1 实现状态

此文件是实现 `docs/architecture/whale-v1-platform-design.md` 的 AI 代理交接清单。

每个代理在开始工作前都必须先阅读此文件。完成一项任务后，要在同一个变更集中更新此文件：将任务标记为完成、补充证据，并把 `Current Task` 移到下一个未完成任务。

## 操作规则

- 一次只处理一个 `Current Task`。
- 除非当前任务被阻塞，否则不要跳到后面的任务。
- 保持现有 CLI 行为、测试和 `.whale/` 制品兼容性不变。
- 默认不要扩大工具权限。
- 在标记任务完成前，运行清单里指定的验证命令。
- 每完成一个功能开发并测试通过后，提交一次 commit 并推送到远端仓库。
- 如果任务被阻塞，把状态标成 `blocked`，写明阻塞原因，并且只有在安全的情况下才把 `Current Task` 切到下一个未阻塞任务。

## 当前任务

- ID: `P5-T1`
- 标题: 通过 worker manager 包装 `delegate`，同时保持子代理只读行为。
- 来源: `whale-v1-platform-design.md`，Phase 5。
- 状态: `in_progress`
- 目标文件:
  - `whale/runtime.py`
  - `whale/tools.py`
  - `whale/workers.py`
  - `tests/test_whale.py`
  - `tests/test_safety_invariants.py`
- 完成标准:
  - `delegate` 执行路径通过 worker manager 封装。
  - 子代理只读行为保持不变。
  - worker depth/step limits 保持兼容。
  - `conda run -n pico python -m pytest -q` 通过。
  - `conda run -n pico ruff check .` 通过。

## 任务队列

| ID | 阶段 | 状态 | 标题 | 验证 | 证据 |
| --- | --- | --- | --- | --- | --- |
| `P1-T1` | Contracts And Documentation | done | 添加 Whale V1 平台设计文档。 | `pytest`, `ruff` | 已添加 `docs/architecture/whale-v1-platform-design.md`；105 个测试通过；Ruff 通过。 |
| `P1-T2` | Contracts And Documentation | done | 为 run/session 制品补充 schema 说明。 | `pytest`, `ruff` | 已新增 `docs/architecture/run-session-schema.md` 并在 `agent-harness-v1-overview.md` 链接；文档覆盖 session、run、trace、report、checkpoint、memory 和 V0 兼容；105 个测试通过；Ruff 通过。 |
| `P2-T1` | Configuration Objects | done | 为 provider、context、tools、workers、memory 和 stores 引入内部配置 dataclass。 | `pytest`, `ruff` | 已添加 `WhaleConfig`、`ProviderProfile`、`ContextConfig`、`ToolConfig`、`WorkerConfig`、`MemoryConfig` 和 `StoreConfig`；`pytest` 109 个测试通过；Ruff 通过。 |
| `P2-T2` | Configuration Objects | done | 在不改变 CLI 行为的前提下，将配置默认值接入 `Whale` 构造。 | `pytest`, `ruff`, `whale --help` | 已将 provider profile 用于 CLI 默认值/env 解析，并通过 `StoreConfig` 装配 session store；`pytest` 111 个测试通过；Ruff 通过；`python -m whale --help` 通过。 |
| `P2-T3` | Context Governance | done | 引入上下文预算、裁剪策略、恢复边界和 trace 事件。 | `pytest`, `ruff` | 已在 prompt metadata 中加入 context policy、budget profile、section floors 和实际裁剪开关；新增 `resume_boundary_evaluated` 与 `context_reduction_applied` trace；`pytest` 112 个测试通过；Ruff 通过。 |
| `P2-T4` | Memory Lifecycle | done | 明确 memory 的加载、更新、压缩、持久化和报告摘要行为，并补测试。 | `pytest`, `ruff` | 已新增 `memory_summary` 并写入 run report，覆盖 working/file summaries/episodic/process/durable/stale invalidation/promotion 计数；`pytest` 113 个测试通过；Ruff 通过。 |
| `P3-T1` | Skill Discovery | done | 添加安全的 `SKILL.md` 发现与 `SkillManifest` 解析。 | `pytest`, `ruff` | 已新增 `whale/skills.py`、`SkillManifest`、三层 discovery roots、front matter 解析、名称校验和裁剪测试；`pytest` 118 个测试通过；Ruff 通过。 |
| `P3-T2` | Skill Discovery | done | 添加确定性的 skill 选择、prompt 注入、元数据和测试。 | `pytest`, `ruff` | 已实现 `$skill` 显式提及、trigger/default 选择、prompt 注入、metadata 和 `skill_selected` trace；`pytest` 122 个测试通过；Ruff 通过。 |
| `P4-T1` | Tool Policy Layer | done | 将工具风险和审批决策抽到 policy 层。 | `pytest`, `ruff` | 已新增 `whale/tool_policy.py` 和 `ToolPolicyDecision`，将未知工具、参数校验、重复调用和审批拒绝从 `run_tool()` 抽离；`pytest` 126 个测试通过；Ruff 通过。 |
| `P4-T2` | Tool Policy Layer | done | 在不改变工具结果的前提下发出 `tool_policy_evaluated` trace 事件。 | `pytest`, `ruff` | 已在工具执行前写入 `tool_policy_evaluated` trace，包含工具名、参数、risk、approval、security、read-only 和路径摘要；`tool_executed` 结果保持兼容；`pytest` 127 个测试通过；Ruff 通过。 |
| `P5-T1` | Worker Manager | in_progress | 通过 worker manager 包装 `delegate`，同时保持子代理只读行为。 | `pytest`, `ruff` | 待完成。 |
| `P5-T2` | Worker Manager | todo | 增加父子 run 关联和 worker trace 汇总事件。 | `pytest`, `ruff` | 待完成。 |
| `P6-T1` | Run Query And Reports | todo | 增加只读辅助方法以列出 runs 并加载 run 摘要。 | `pytest`, `ruff` | 待完成。 |
| `P6-T2` | Run Query And Reports | todo | 扩展报告，加入 provider、skills、worker 和 memory 摘要。 | `pytest`, `ruff` | 待完成。 |

## 完成更新模板

完成某项任务时，更新：

```text
## Current Task
- ID: <next task id>
- Title: <next task title>
- Source: <design doc phase>
- Status: in_progress
- Target files:
  - <expected files>
- Done when:
  - <acceptance checks>
```

然后更新 `Task Queue` 中已完成的行：

```text
| `<task id>` | <phase> | done | <title> | `pytest`, `ruff` | <简短证据和关键文件> |
```

## 阻塞日志

当前没有活动阻塞。
