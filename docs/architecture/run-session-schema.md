# Run And Session Artifact Schema

This document records the current `.whale/` artifact contract used by Whale v1. It describes the files the runtime already writes today; it does not require a storage migration or a CLI behavior change.

## Storage Layout

Whale keeps resumable conversation state separate from per-request audit artifacts:

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

`.whale/sessions/<session_id>.json` is the resumable session state. `.whale/runs/<run_id>/` is the immutable-by-convention audit bundle for one `Whale.ask()` call. `.whale/memory/` stores durable topic notes that are referenced by session memory but are not embedded in each run artifact.

## Versioning And Compatibility

Existing run and session artifacts do not carry a top-level schema version. Whale v1 treats those files as V0-compatible input and keeps reading them with defensive defaults:

- Missing session `history` becomes an empty list.
- Missing session `memory` becomes the default memory state.
- Missing session `checkpoints`, `runtime_identity`, or `resume_state` is rebuilt on load.
- Missing task fields are normalized by `TaskState.from_dict()` when loaded through runtime helpers.
- Missing `report.json` is tolerated for interrupted runs; `task_state.json` and `trace.jsonl` may still exist.

New checkpoint objects already carry `schema_version: "phase1-v1"`. Future artifact versions should add version fields without breaking V0 reads.

## Session File

Path:

```text
.whale/sessions/<session_id>.json
```

Current fields:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Stable session id, also used as the session filename. |
| `created_at` | string | ISO-like timestamp from runtime `now()`. |
| `workspace_root` | string | Workspace root used when the session was created. |
| `history` | array | Conversation and tool history used to build later prompts. |
| `memory` | object | Normalized session memory state. See `Session Memory`. |
| `checkpoints` | object | Current checkpoint pointer and checkpoint bodies. |
| `runtime_identity` | object | Last known runtime identity used for resume checks. |
| `resume_state` | object | Last resume evaluation result. |

History entries are dictionaries written by `Whale.record()`:

| Field | Type | Notes |
| --- | --- | --- |
| `role` | string | Usually `user`, `assistant`, or `tool`. |
| `content` | string | User text, assistant text, or tool result. |
| `created_at` | string | Timestamp for the history item. |
| `name` | string | Tool name, only present on tool entries. |
| `args` | object | Tool arguments, only present on tool entries. |

## Session Memory

The `memory` object is normalized on load. Current fields:

| Field | Type | Notes |
| --- | --- | --- |
| `working` | object | Compact working state for the current or latest task. |
| `working.task_summary` | string | Latest task summary, clipped to the memory budget. |
| `working.recent_files` | array | Canonical workspace-relative paths. |
| `episodic_notes` | array | Small notes from recent interactions. |
| `file_summaries` | object | Path-keyed file summaries with freshness hashes. |
| `task` | string | Backward-compatible alias of `working.task_summary`. |
| `files` | array | Backward-compatible alias of `working.recent_files`. |
| `notes` | array | Backward-compatible list of episodic note text. |
| `next_note_index` | integer | Monotonic note index for deterministic ranking. |
| `durable_topics` | array | Topic slugs discovered under `.whale/memory/`. |

Each `episodic_notes` item:

| Field | Type | Notes |
| --- | --- | --- |
| `text` | string | Clipped note body. |
| `tags` | array | Search and retrieval tags. |
| `source` | string | Source path, tool name, or empty string. |
| `created_at` | string | Timestamp used for ranking. |
| `note_index` | integer | Tie-breaker for deterministic retrieval. |
| `kind` | string | Usually `episodic`, `process`, or `durable`. |

Each `file_summaries` value:

| Field | Type | Notes |
| --- | --- | --- |
| `summary` | string | Short summary of a read file. |
| `created_at` | string | Timestamp when the summary was written. |
| `freshness` | string or null | SHA-256 hash of the file content when summarized. |

V0 memory compatibility keeps older `task`, `files`, and `notes` fields readable by lifting them into the normalized `working` and `episodic_notes` shapes when needed.

## Checkpoints

Checkpoints are stored inside the session file, not as separate run files:

```json
{
  "checkpoints": {
    "current_id": "ckpt_12345678",
    "items": {
      "ckpt_12345678": {}
    }
  }
}
```

Current checkpoint fields:

| Field | Type | Notes |
| --- | --- | --- |
| `checkpoint_id` | string | Checkpoint id, usually `ckpt_<hex>`. |
| `parent_checkpoint_id` | string | Previous checkpoint id when available. |
| `schema_version` | string | Currently `phase1-v1`. |
| `created_at` | string | Creation timestamp. |
| `current_goal` | string | User request or current goal text. |
| `completed` | array | Completed items or final answer snippets. |
| `excluded` | array | Explicitly excluded work. |
| `current_blocker` | string | Stop reason or blocker when the run did not finish cleanly. |
| `next_step` | string | Resume hint. |
| `key_files` | array | Objects with `path` and `freshness`. |
| `freshness` | object | Path-to-freshness map for quick checks. |
| `summary` | string | Short checkpoint summary. |
| `runtime_identity` | object | Runtime details used for resume compatibility checks. |

Run artifacts only reference checkpoints through `checkpoint_id`; they do not duplicate checkpoint body fields such as `current_goal`.

## Run Directory

Path:

```text
.whale/runs/<run_id>/
```

`run_id` is generated as `run_YYYYMMDD-HHMMSS-<hex>`. Each run directory may contain a partial set of files if the process exits early. A normal completed run has all three files below.

## task_state.json

`task_state.json` is rewritten during the run and stores the current state machine snapshot:

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | string | Run id and run directory name. |
| `task_id` | string | Separate task id generated for this user request. |
| `user_request` | string | Full request passed to `Whale.ask()`. |
| `status` | string | `running`, `completed`, `stopped`, or `failed`. |
| `tool_steps` | integer | Number of tool calls that entered execution. |
| `attempts` | integer | Number of model attempts. |
| `last_tool` | string | Last requested tool name. |
| `stop_reason` | string | Machine-readable stop reason. |
| `final_answer` | string | Final answer or stop message when available. |
| `checkpoint_id` | string | Latest checkpoint id referenced by this run. |
| `resume_status` | string | Resume status at run start. |

Known stop reasons include `final_answer_returned`, `step_limit_reached`, `retry_limit_reached`, `model_error`, `tool_timeout`, `approval_denied`, `delegate_failed`, `persistence_error`, and `resume_load_error`.

## trace.jsonl

`trace.jsonl` is append-only JSON Lines. Each line is one event object. All trace payloads are redacted before writing.

Required base fields:

| Field | Type | Notes |
| --- | --- | --- |
| `event` | string | Event name. |
| `created_at` | string | Event timestamp added by `emit_trace()`. |

Current event names include:

- `run_started`
- `prompt_built`
- `model_requested`
- `model_parsed`
- `tool_executed`
- `checkpoint_created`
- `runtime_identity_mismatch`
- `run_finished`

Common payload fields:

| Event | Fields |
| --- | --- |
| `run_started` | `task_id`, clipped `user_request` |
| `prompt_built` | `prompt_metadata`, `duration_ms` |
| `model_requested` | `attempts`, `tool_steps`, `prompt_cache_key` |
| `model_parsed` | `kind`, `completion_metadata`, `duration_ms` |
| `tool_executed` | `name`, `args`, clipped `result`, `duration_ms`, `tool_status`, `tool_error_code`, `security_event_type`, `risk_level`, `read_only`, `affected_paths`, `workspace_changed`, `workspace_fingerprint`, `diff_summary` |
| `checkpoint_created` | `checkpoint_id`, `trigger` |
| `runtime_identity_mismatch` | `fields` |
| `run_finished` | `status`, `stop_reason`, `final_answer`, `run_duration_ms` |

`prompt_metadata` includes section-level context metadata such as raw/rendered chars, budget reductions, selected relevant memory, prompt cache key, workspace fingerprint, tool signature, resume status, stale paths, and redacted secret environment summaries.

## report.json

`report.json` is written at run finalization and stores the final summary. It is also redacted before writing.

Current fields:

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | string | Run id. |
| `task_id` | string | Task id. |
| `status` | string | Final task status. |
| `stop_reason` | string | Final stop reason. |
| `final_answer` | string | Final answer or stop message. |
| `tool_steps` | integer | Final tool step count. |
| `attempts` | integer | Final model attempt count. |
| `checkpoint_id` | string | Latest checkpoint id. |
| `resume_status` | string | Resume status captured on the task state. |
| `task_state` | object | Embedded `TaskState.to_dict()` snapshot. |
| `prompt_metadata` | object | Last prompt metadata from the run. |
| `durable_promotions` | array | Durable memory notes promoted by the final answer. |
| `durable_rejections` | array | Durable memory promotion rejections. |
| `durable_superseded` | array | Durable memory notes replaced by newer notes. |
| `redacted_env` | object | Secret environment detection summary. |

The report is a run summary, not a full event log. Use `trace.jsonl` for step-by-step reconstruction.

## Durable Memory Files

Durable memory lives under `.whale/memory/` and is separate from session JSON:

| Path | Notes |
| --- | --- |
| `.whale/memory/MEMORY.md` | Markdown index of durable topics. |
| `.whale/memory/topics/<topic>.md` | Topic metadata plus `## Notes` bullet list. |

Known topic slugs are `project-conventions`, `key-decisions`, `dependency-facts`, and `user-preferences`. Durable memory is only written when the user request expresses explicit durable-memory intent and the final answer contains accepted structured lines such as `Project convention: ...`, `Decision: ...`, `Dependency: ...`, or `Preference: ...`.

## Redaction Expectations

Trace and report artifacts are passed through runtime redaction before writing. Values from configured secret environment variables are replaced with `<redacted>`. The session file stores local conversation state and memory; callers should still avoid placing secrets in prompts or durable memory.

## V1 Evolution Rules

- Keep `.whale/sessions/` and `.whale/runs/<run_id>/` paths stable.
- Keep V0 files without schema versions readable.
- Add version fields compatibly before changing artifact shapes.
- Keep checkpoint bodies in session storage unless a future migration explicitly documents otherwise.
- Do not require migration before reading existing local `.whale/` state.
