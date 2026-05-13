# Whale V1 Implementation Status

This file is the handoff ledger for AI agents implementing `docs/architecture/whale-v1-platform-design.md`.

Every agent must read this file before starting work. After finishing one task, update this file in the same change set: mark the task complete, add evidence, and move `Current Task` to the next unchecked task.

## Operating Rules

- Work on exactly one `Current Task` at a time.
- Do not skip ahead unless the current task is blocked.
- Keep existing CLI behavior, tests, and `.whale/` artifact compatibility.
- Do not broaden tool permissions by default.
- Run the listed validation before marking a task complete.
- If a task is blocked, mark it `blocked`, write the blocker, and set `Current Task` to the next unblocked task only if doing so is safe.

## Current Task

- ID: `P1-T2`
- Title: Add schema notes for run/session artifacts.
- Source: `whale-v1-platform-design.md`, Phase 1.
- Status: `in_progress`
- Target files:
  - `docs/architecture/agent-harness-v1-overview.md`
  - optionally `docs/architecture/run-session-schema.md`
- Done when:
  - Existing `.whale/sessions/` and `.whale/runs/<run_id>/` artifacts are documented.
  - `task_state.json`, `trace.jsonl`, `report.json`, checkpoints, and session memory are described.
  - Compatibility expectations for V0 files without schema versions are stated.
  - `conda run -n pico python -m pytest -q` passes.
  - `conda run -n pico ruff check .` passes.

## Task Queue

| ID | Phase | Status | Title | Validation | Evidence |
| --- | --- | --- | --- | --- | --- |
| `P1-T1` | Contracts And Documentation | done | Add Whale V1 platform design document. | `pytest`, `ruff` | Added `docs/architecture/whale-v1-platform-design.md`; 105 tests passed; Ruff passed. |
| `P1-T2` | Contracts And Documentation | in_progress | Add schema notes for run/session artifacts. | `pytest`, `ruff` | Pending. |
| `P2-T1` | Configuration Objects | todo | Introduce internal config dataclasses for provider, context, tools, workers, memory, and stores. | `pytest`, `ruff` | Pending. |
| `P2-T2` | Configuration Objects | todo | Wire config defaults into `Whale` construction without changing CLI behavior. | `pytest`, `ruff`, `whale --help` | Pending. |
| `P3-T1` | Skill Discovery | todo | Add safe `SKILL.md` discovery and `SkillManifest` parsing. | `pytest`, `ruff` | Pending. |
| `P3-T2` | Skill Discovery | todo | Add deterministic skill selection, prompt injection, metadata, and tests. | `pytest`, `ruff` | Pending. |
| `P4-T1` | Tool Policy Layer | todo | Extract tool risk and approval decisions into a policy layer. | `pytest`, `ruff` | Pending. |
| `P4-T2` | Tool Policy Layer | todo | Emit `tool_policy_evaluated` trace events without changing tool results. | `pytest`, `ruff` | Pending. |
| `P5-T1` | Worker Manager | todo | Wrap `delegate` through a worker manager while preserving read-only child behavior. | `pytest`, `ruff` | Pending. |
| `P5-T2` | Worker Manager | todo | Add parent/child run linkage and worker trace summary events. | `pytest`, `ruff` | Pending. |
| `P6-T1` | Run Query And Reports | todo | Add read-only helpers to list runs and load run summaries. | `pytest`, `ruff` | Pending. |
| `P6-T2` | Run Query And Reports | todo | Extend reports with provider, skills, worker, and memory summaries. | `pytest`, `ruff` | Pending. |

## Completion Update Template

When completing a task, update:

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

Then update the finished row in `Task Queue`:

```text
| `<task id>` | <phase> | done | <title> | `pytest`, `ruff` | <short evidence and key files> |
```

## Blocker Log

No active blockers.

