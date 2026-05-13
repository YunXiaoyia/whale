# Whale V1 总结

Whale V1 保留现有 CLI 和 `.whale/` 存储布局，同时把运行时拆成更清晰的配置、上下文、工具策略、skill、worker、memory 和 run 制品边界。

## 使用说明

启动方式保持兼容：

```bash
python -m whale --cwd . --provider openai
python -m whale --cwd . --provider ollama --model qwen3.5:4b
python -m whale --cwd . --approval auto "Inspect README.md"
```

常用 provider 环境变量继续可用：

- `WHALE_OPENAI_API_BASE`、`WHALE_OPENAI_API_KEY`、`WHALE_OPENAI_MODEL`
- `WHALE_ANTHROPIC_API_BASE`、`WHALE_ANTHROPIC_API_KEY`、`WHALE_ANTHROPIC_MODEL`
- `WHALE_DEEPSEEK_API_BASE`、`WHALE_DEEPSEEK_API_KEY`、`WHALE_DEEPSEEK_MODEL`

运行制品仍写入 `.whale/runs/<run_id>/`：

- `task_state.json`：当前 run 状态、checkpoint、worker 关联。
- `trace.jsonl`：逐事件审计时间线。
- `report.json`：最终摘要，包含 provider、skills、workers 和 memory 摘要。

只读查询接口：

```python
from whale.run_store import RunStore

store = RunStore(".whale/runs")
runs = store.list_runs()
summary = store.load_run_summary(runs[0]["run_id"])
```

## 更新说明

配置层新增 `WhaleConfig`，覆盖 provider、runtime、context、tools、workers、memory、skills 和 stores 的内部默认值。CLI 行为和已有环境变量保持不变。

上下文治理新增预算、section floors、恢复边界和 trace 元数据。发生上下文裁剪或恢复状态变化时，run trace 会记录对应事件。

Memory 生命周期更明确：working memory、file summaries、episodic notes 和 durable topics 分层管理，report 会输出 `memory_summary`，durable promotion 仍要求显式 intent。

Skill 支持本地 `SKILL.md` 发现和确定性选择。Skill 只作为 prompt 指令注入，不执行代码；trace/report 只记录名称、来源和摘要元数据，不记录完整 instruction body。

工具策略从 `run_tool()` 中抽成 `ToolPolicy`，每次工具执行前会写入 `tool_policy_evaluated`，工具返回和 `tool_executed` 兼容既有行为。

`delegate` 由 `WorkerManager` 管理。Worker 默认只读、继承 provider client 和 workspace、共享 run store、拥有独立 run/task state；父 run 记录 `worker_started` 和 `worker_finished` 汇总事件。

Report 现在包含：

- `provider_summary`
- `skills_summary`
- `worker_summary`
- `memory_summary`

这些字段是向后兼容的新增字段；已有 `task_state`、`prompt_metadata`、`durable_promotions` 等字段继续保留。

## 验证

V1 交付时的验证命令：

```bash
conda run -n pico python -m pytest -q
conda run -n pico ruff check .
```
