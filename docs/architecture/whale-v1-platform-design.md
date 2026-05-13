# Whale V1 Platform Design

## Summary

Whale V1 keeps the current command-line user experience and `.whale/` storage layout while turning the runtime into a clearer platform boundary. The goal is not to add a second agent system beside the current one. The goal is to formalize the capabilities already present in `Whale.ask()`, `ContextManager`, `RunStore`, `tools.py`, provider clients, delegation, and memory into stable subsystems that can be extended without making the control loop harder to reason about.

V1 should remain compatible with:

- The `whale` CLI and `python -m whale` entrypoints.
- Existing `WHALE_*` provider environment variables.
- Existing `.whale/sessions/` and `.whale/runs/<run_id>/` directories.
- Existing run artifacts: `task_state.json`, `trace.jsonl`, and `report.json`.
- The existing `FakeModelClient`-based tests that validate behavior without real providers.

## Current Baseline

Whale already has the first version of most requested capabilities:

- Task run records: `RunStore`, `TaskState`, trace events, reports, checkpoints.
- Context governance: `ContextManager` with section budgets, reduction order, and prompt metadata.
- Tool safety: explicit tool registry, path sandboxing, approval modes, secret redaction, allowlisted shell environment.
- Multi-provider support: Ollama, OpenAI-compatible, Anthropic-compatible, and DeepSeek-compatible clients.
- Worker behavior: `delegate` creates a bounded read-only child agent.
- Memory: working memory, file summaries, episodic notes, durable topics, freshness invalidation, and promotion rules.

The main V1 gaps are:

- These capabilities are configured indirectly through constructor arguments and constants.
- Run records do not expose a single schema contract.
- Tool policy is mixed into `Whale.run_tool()`.
- Provider configuration is spread between CLI defaults, environment variables, and model client setup.
- Delegation is a tool implementation rather than a worker-management subsystem.
- Skill discovery does not exist yet.

## Design Principles

- Compatibility first: existing CLI commands, local artifacts, and tests remain valid.
- Safety by default: no new feature should expand tool authority unless explicitly configured.
- Text before code execution: skills are prompt instructions in V1, not executable plugins.
- Observability everywhere: each major subsystem emits trace/report metadata.
- Small interfaces: add stable data contracts before adding advanced behavior.
- Deterministic tests: all new behavior must be testable with fake clients and local fixtures.

## Runtime And Run Records

The runtime should keep `Whale.ask()` as the main public execution method, but V1 should treat each request as a structured run.

### Responsibilities

- `SessionStore` stores recoverable conversation state.
- `RunStore` stores audit artifacts for one user request.
- `TaskState` stores current execution status.
- Checkpoints store resumability hints and runtime identity.
- Trace events store the step-by-step timeline.
- Reports store final summaries and metrics.

### V1 Contract

Run artifacts stay in the current locations:

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

Each artifact should include or preserve a schema version. Existing files without a version should be treated as V0-compatible input.

Suggested stable record names:

- `RunRecord`: run id, task id, session id, workspace root, created timestamps, status, stop reason, artifact paths.
- `TaskRecord`: user request, attempts, tool steps, last tool, final answer, checkpoint id, resume status.
- `TraceEvent`: event name, created_at, payload, redaction state.
- `RunReport`: final task state, prompt metadata, tool summary, memory summary, worker summary, provider metadata.

### Trace Events

The existing events should remain valid:

- `run_started`
- `prompt_built`
- `model_requested`
- `model_parsed`
- `tool_executed`
- `checkpoint_created`
- `run_finished`

V1 can add these events:

- `skill_selected`
- `tool_policy_evaluated`
- `worker_started`
- `worker_finished`
- `memory_promoted`
- `provider_selected`

## Context Governance

`ContextManager` should become the formal context policy layer. It already builds prompts from prefix, memory, relevant memory, history, and the current request.

### Sections

V1 keeps the existing section order:

```text
prefix
memory
relevant_memory
history
current_request
```

V1 can add optional skill content inside `prefix` or as a new `skills` section before `memory`. To preserve compatibility, the default should inject skills into `prefix` unless a new schema version is explicitly enabled.

### Policy

The context policy should expose:

- Total prompt budget.
- Per-section budgets.
- Per-section floors.
- Reduction order.
- Relevant memory limit.
- Skill instruction budget.
- Whether context reduction is enabled.

### Metadata

Every prompt build should continue to report:

- Raw and rendered chars per section.
- Applied reductions.
- Selected relevant memory notes.
- Prompt cache key.
- Workspace fingerprint.
- Tool signature.

V1 should add:

- Selected skill names and sources.
- Context policy name.
- Budget profile name.

## Skill System

Skills are the largest new subsystem. V1 should keep them simple and safe: a skill is a local markdown instruction file, not executable code.

### Discovery Paths

Default discovery order:

```text
<repo>/skills/
<repo>/.whale/skills/
~/.whale/skills/
```

Only files named `SKILL.md` are loaded in V1. Nested skill directories are allowed.

### Skill Manifest

Each skill should be represented internally as `SkillManifest`:

- `name`: stable skill id.
- `description`: short user-facing summary.
- `triggers`: words or phrases that make the skill relevant.
- `source_path`: absolute path to the `SKILL.md`.
- `scope`: `project` or `user`.
- `instructions`: clipped markdown content.
- `enabled`: boolean.

### Selection

Skill selection should be deterministic:

- Match explicit skill mentions first, such as `$python-testing`.
- Then match trigger words in the current user request.
- Then include project-default skills if configured.
- Limit selected skills by count and character budget.

### Prompt Injection

Selected skills should be rendered as concise instructions:

```text
Selected skills:
- <name>: <description>
  Source: <relative path>
  Instructions:
  <clipped body>
```

V1 should not execute scripts referenced by skills. It only tells the model about available workflows.

### Safety

- Skills outside discovery roots are ignored.
- Skill content is clipped.
- Skill names must be simple path-safe identifiers.
- Trace events record skill selection, not full private skill content unless explicitly configured.

## Tool Safety Policy

The current tool model is a good base: explicit registry, schema validation, risky flag, approval mode, path sandboxing, and environment allowlist.

V1 should separate policy decisions from tool execution without changing user behavior.

### Tool Policy Fields

Suggested `ToolPolicy` fields:

- `tool_name`
- `risk_level`: `low`, `medium`, `high`
- `approval`: `never`, `ask`, `auto`
- `read_only`
- `allowed_paths`
- `denied_paths`
- `shell_env_allowlist`
- `timeout_limit`
- `max_output_chars`
- `repeat_call_policy`

### Default Policy

Preserve current behavior:

- `list_files`, `read_file`, `search`, and `delegate` are low-risk.
- `run_shell`, `write_file`, and `patch_file` are high-risk.
- `--approval ask` asks before high-risk tools.
- `--approval auto` allows high-risk tools.
- `--approval never` denies high-risk tools.
- Read-only child agents cannot run risky tools.

### Audit

Each tool call should emit a `tool_policy_evaluated` event before execution, containing:

- Tool name.
- Risk level.
- Approval decision.
- Security event type.
- Read-only state.
- Affected path if known.

Existing `tool_executed` metadata remains the final execution result.

## Multi-Provider Configuration

Provider setup currently lives mostly in `cli.py` and model client constructors. V1 should add a provider profile layer while preserving all existing environment variables.

### Existing Providers

- `ollama`
- `openai`
- `anthropic`
- `deepseek`

### Provider Profile

Suggested `ProviderProfile` fields:

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

### Config Sources

Priority remains:

```text
CLI args > .env WHALE_* variables > legacy environment variables > defaults
```

V1 can add optional config files later, but should not require them.

### Compatibility

The current variables remain valid:

- `WHALE_OPENAI_API_BASE`
- `WHALE_OPENAI_API_KEY`
- `WHALE_OPENAI_MODEL`
- `WHALE_ANTHROPIC_API_BASE`
- `WHALE_ANTHROPIC_API_KEY`
- `WHALE_ANTHROPIC_MODEL`
- `WHALE_DEEPSEEK_API_BASE`
- `WHALE_DEEPSEEK_API_KEY`
- `WHALE_DEEPSEEK_MODEL`

## Worker Management

V1 should formalize `delegate` as worker management. It should not introduce true parallel execution yet.

### Worker Model

Suggested `WorkerSpec` fields:

- `worker_id`
- `parent_run_id`
- `task`
- `read_only`
- `max_steps`
- `allowed_tools`
- `depth`
- `max_depth`
- `workspace_root`

### Behavior

Default V1 behavior:

- Workers are read-only.
- Workers inherit provider client and workspace.
- Workers share run store but have their own task/run state.
- Worker depth remains bounded.
- Worker result returns as text to the parent.

### Trace Integration

Parent traces should record:

- `worker_started`
- `worker_finished`
- Worker run id.
- Worker status.
- Clipped worker final answer.

Worker traces remain in their own run directory.

## Memory Mechanism

The existing `LayeredMemory` model is preserved and made explicit.

### Layers

- Working memory: current task summary and recent files.
- File summaries: short summaries keyed by canonical workspace path and freshness hash.
- Episodic notes: short notes from recent interactions.
- Durable memory: topic files under `.whale/memory/topics/`.

### Policy

Suggested `MemoryPolicy` fields:

- Working file limit.
- Episodic note limit.
- File summary limit.
- Relevant memory retrieval limit.
- Durable topic allowlist.
- Promotion patterns.
- Rejection rules.
- Freshness invalidation enabled.

### Promotion

V1 keeps explicit durable promotion intent:

- English intent: capture, remember, save, store, persist, note.
- Chinese intent: 记住, 保存, 记录, 沉淀, 长期记忆, 持久记忆.

Promotion still requires structured final-answer lines such as:

```text
Project convention: ...
Decision: ...
Dependency: ...
Preference: ...
```

### Safety

Durable memory should reject:

- Secret-shaped text.
- Transient task state.
- Long noisy stdout/stderr/traceback content.
- Redacted values.

## Proposed Public Interfaces

These names are design targets for V1 implementation. They do not need to be public imports immediately.

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

## Implementation Phases

### Phase 1: Contracts And Documentation

- Add this platform design.
- Add schema notes to run/session docs.
- Keep behavior unchanged.

### Phase 2: Configuration Objects

- Introduce internal config dataclasses.
- Convert constructor constants into config defaults.
- Preserve all current CLI arguments.

### Phase 3: Skill Discovery

- Add skill loader and deterministic selector.
- Inject selected skill text into prompt metadata and prefix.
- Add tests for discovery, selection, clipping, and trace metadata.

### Phase 4: Tool Policy Layer

- Extract approval/risk decisions from `run_tool()`.
- Add `tool_policy_evaluated` trace events.
- Keep existing tool execution results unchanged.

### Phase 5: Worker Manager

- Wrap `delegate` in worker manager functions.
- Add parent/child run linkage.
- Add worker trace summary events.

### Phase 6: Run Query And Reports

- Add read-only helpers to list runs and load run summaries.
- Extend reports with provider, skills, worker, and memory summaries.

## Acceptance Criteria

- Existing tests keep passing.
- `whale --help` remains valid.
- Existing `.env.example` remains valid.
- Existing `.whale/runs/<run_id>/task_state.json`, `trace.jsonl`, and `report.json` remain readable.
- Skills cannot execute code in V1.
- Workers are read-only by default.
- Tool policy decisions are traceable.
- Provider selection is visible in trace/report metadata.
- Memory promotion remains explicit and rejects secret-shaped content.

## Non-Goals For V1

- True parallel worker execution.
- Remote skill marketplaces.
- Executable plugins.
- Database-backed run storage.
- Breaking changes to CLI flags.
- Migration requirement for existing `.whale/` state.

