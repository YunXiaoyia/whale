# Whale Review Pack

## Project pitch

Whale is a small local coding agent that runs in a terminal, inspects a repository, calls bounded tools, and records each run locally.

## Architecture map

- `whale/cli.py`: command-line argument parsing and runtime assembly.
- `whale/runtime.py`: agent control loop, tool execution gate, trace/report writing.
- `whale/tools.py`: explicit tool registry and tool implementations.
- `whale/models.py`: provider clients behind one completion interface.
- `whale/context_manager.py`: prompt assembly and context budget control.
- `whale/memory.py`: working memory, file summaries, and durable memory.

## Benchmark evidence

Benchmark fixtures and task definitions live under `benchmarks/` and `tests/fixtures/`. The test suite uses `FakeModelClient` for deterministic agent-loop coverage without real model calls.

## Sample run artifact list

Each run writes local artifacts under `.whale/runs/<run_id>/`:

- `task_state.json`
- `trace.jsonl`
- `report.json`
