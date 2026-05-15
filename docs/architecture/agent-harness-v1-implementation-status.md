# Agent Harness V1 实现状态

此文件是实现 Agent Harness V1 的 AI 代理交接清单。Harness V1 的目标是把现有 `Whale.ask()` 运行循环和 deterministic benchmark 评测能力包装成明确的 runtime harness 与 eval harness 接口，同时保持现有 `whale` CLI、`.whale/` 制品和测试行为兼容。

每个代理在开始工作前都必须先阅读此文件。完成一项任务后，要在同一个变更集中更新此文件：将任务标记为完成、补充证据，并把 `Current Task` 移到下一个未完成任务。

## 操作规则

- 一次只处理一个 `Current Task`。
- 除非当前任务被阻塞，否则不要跳到后面的任务。
- 保持现有 `whale` CLI 行为、测试和 `.whale/` 制品兼容性不变。
- 本阶段不要拆分或重写 `Whale.ask()` 主循环；runtime harness 只做薄编排层。
- Eval harness 复用现有 `BenchmarkEvaluator` 和 `run_harness_regression_v2()`，不要引入新的 benchmark schema。
- 默认输出路径应继续落在已忽略的本地目录：`.whale/` 和 `artifacts/`。
- 在标记任务完成前，运行清单里指定的验证命令。
- 如果任务被阻塞，把状态标成 `blocked`，写明阻塞原因，并且只有在安全的情况下才把 `Current Task` 切到下一个未阻塞任务。

## 当前任务

- ID: `HARNESS-V1-COMPLETE`
- 标题: Agent Harness V1 完成。
- 来源: Agent Harness V1。
- 状态: `done`
- 目标文件:
  - 无
- 完成标准:
  - 所有任务队列项均为 `done`。
  - `pytest -q` 通过。
  - `ruff check .` 通过。

## 任务队列

| ID | 阶段 | 状态 | 标题 | 验证 | 证据 |
| --- | --- | --- | --- | --- | --- |
| `H1-T1` | Runtime Harness API | done | 添加 `RuntimeHarness` 和 `HarnessRunResult`。 | `pytest tests/test_harness.py -q` | 已新增 `whale/harness.py`、导出 `RuntimeHarness`/`HarnessRunResult`，并覆盖 JSON-ready 摘要与 run artifact 路径；`conda activate whale && python -m pytest tests/test_harness.py -q` 通过。 |
| `H1-T2` | Eval Harness API | done | 添加 `EvaluationHarness`，包装现有 `BenchmarkEvaluator` 和 `run_harness_regression_v2()`。 | `pytest tests/test_evaluator.py tests/test_harness.py -q` | 已新增 `EvaluationHarness`，默认写 `artifacts/harness-regression-v2.json`，并保留 `BenchmarkEvaluator` 复用入口；`conda activate whale && python -m pytest tests/test_evaluator.py tests/test_harness.py -q` 通过。 |
| `H2-T1` | Harness CLI | done | 添加 `whale-harness run`，输出 runtime harness JSON 摘要。 | `pytest tests/test_harness_cli.py -q` | 已新增 `whale/harness_cli.py` 的 `run` 子命令，复用 `build_agent()` 与 `RuntimeHarness.run()` 输出 JSON；`conda activate whale && python -m pytest tests/test_harness_cli.py -q` 通过。 |
| `H2-T2` | Harness CLI | done | 添加 `whale-harness eval`，运行 deterministic harness regression 并写 artifact。 | `pytest tests/test_harness_cli.py tests/test_evaluator.py -q` | 已新增 `eval` 子命令，复用 `EvaluationHarness` 并支持 `--artifact-path`/`--workspace-root`；`conda activate whale && python -m pytest tests/test_harness_cli.py tests/test_evaluator.py -q` 通过。 |
| `H3-T1` | Packaging | done | 导出 harness API，并在 `pyproject.toml` 添加 `whale-harness` console script。 | `python -m whale --help`, `whale-harness --help` | `RuntimeHarness`、`HarnessRunResult`、`EvaluationHarness` 已从 `whale` 导出，并新增 `whale-harness = "whale.harness_cli:main"`；两条 help 命令在 `conda activate whale` 后通过。 |
| `H3-T2` | Documentation | done | 更新 README，并从 `agent-harness-v1-overview.md` 链接到本实现状态文档。 | 文档 review | README 已说明 public harness API 与 `whale-harness` CLI；overview 已链接本实现状态文档；完成链接与片段 review。 |
| `H4-T1` | Final Verification | done | 运行完整测试和 lint，标记 Agent Harness V1 完成。 | `pytest -q`, `ruff check .` | `conda activate whale && python -m pytest -q` 通过，141 passed；`conda activate whale && ruff check .` 通过。 |

## 接口目标

Runtime harness 目标 JSON 形状：

```json
{
  "schema_version": 1,
  "answer": "Done.",
  "run_id": "run_...",
  "task_id": "task_...",
  "status": "completed",
  "stop_reason": "final_answer_returned",
  "tool_steps": 1,
  "attempts": 2,
  "run_dir": ".whale/runs/run_...",
  "task_state_path": ".whale/runs/run_.../task_state.json",
  "trace_path": ".whale/runs/run_.../trace.jsonl",
  "report_path": ".whale/runs/run_.../report.json"
}
```

计划中的 CLI 示例：

```bash
whale-harness run --provider deepseek --approval auto "检查这个仓库"
whale-harness eval --artifact-path artifacts/harness-regression-v2.json
```

## 完成更新模板

完成某项任务时，更新：

```text
## 当前任务

- ID: <next task id>
- 标题: <next task title>
- 来源: <phase>
- 状态: todo
- 目标文件:
  - <expected files>
- 完成标准:
  - <acceptance checks>
```

然后更新 `任务队列` 中已完成的行：

```text
| `<task id>` | <phase> | done | <title> | `<verification>` | <简短证据和关键文件> |
```

如果所有任务完成，将 `当前任务` 更新为：

```text
- ID: `HARNESS-V1-COMPLETE`
- 标题: Agent Harness V1 完成。
- 来源: Agent Harness V1。
- 状态: `done`
- 目标文件:
  - 无
- 完成标准:
  - 所有任务队列项均为 `done`。
  - `pytest -q` 通过。
  - `ruff check .` 通过。
```

## 阻塞日志

当前没有活动阻塞。
