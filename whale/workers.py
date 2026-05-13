"""Worker management for bounded delegate calls."""

import time
import uuid
from dataclasses import dataclass, replace

from .config import DEFAULT_WORKER_CONFIG
from .workspace import clip


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    parent_run_id: str
    run_id: str
    task: str
    read_only: bool
    max_steps: int
    allowed_tools: tuple[str, ...]
    depth: int
    max_depth: int
    workspace_root: str


class WorkerManager:
    def __init__(self, parent_agent, config=None):
        self.parent_agent = parent_agent
        self.config = config or DEFAULT_WORKER_CONFIG
        self.last_worker_spec = None

    def can_delegate(self):
        if not bool(getattr(self.config, "enabled", True)):
            return False
        return self.parent_agent.depth < self.parent_agent.max_depth

    def validate_delegate(self, args):
        self._task(args)
        if not self.can_delegate():
            raise ValueError("delegate depth exceeded")

    def delegate(self, args):
        spec = self.build_spec(args)
        child = self.build_child(spec)
        spec = replace(spec, allowed_tools=self.allowed_tools(child))
        self.last_worker_spec = spec

        child.session["memory"]["task"] = spec.task
        child.session["memory"]["notes"] = [clip(self.parent_agent.history_text(), 300)]
        self.record_worker(
            spec,
            {
                "status": "running",
                "final_answer": "",
                "duration_ms": 0,
            },
        )
        self.emit_parent_trace("worker_started", spec, {"status": "running"})
        started_at = time.monotonic()
        answer = child.ask(spec.task, run_id=spec.run_id, parent_run_id=spec.parent_run_id, worker_id=spec.worker_id)
        summary = {
            "status": child.current_task_state.status if child.current_task_state else "",
            "final_answer": clip(answer, 500),
            "duration_ms": int((time.monotonic() - started_at) * 1000),
        }
        self.record_worker(spec, summary)
        self.emit_parent_trace("worker_finished", spec, summary)
        return "delegate_result:\n" + answer

    def build_spec(self, args):
        self.validate_delegate(args)
        task = self._task(args)
        max_steps = int(args.get("max_steps", getattr(self.config, "default_max_steps", DEFAULT_WORKER_CONFIG.default_max_steps)))
        task_state = getattr(self.parent_agent, "current_task_state", None)
        return WorkerSpec(
            worker_id="worker_" + uuid.uuid4().hex[:12],
            parent_run_id=str(getattr(task_state, "run_id", "") or ""),
            run_id=self.parent_agent.new_run_id(),
            task=task,
            read_only=True,
            max_steps=max_steps,
            allowed_tools=(),
            depth=self.parent_agent.depth + 1,
            max_depth=self.parent_agent.max_depth,
            workspace_root=str(self.parent_agent.root),
        )

    def build_child(self, spec):
        from .runtime import Whale

        return Whale(
            model_client=self.parent_agent.model_client,
            workspace=self.parent_agent.workspace,
            session_store=self.parent_agent.session_store,
            run_store=self.parent_agent.run_store,
            approval_policy="never",
            max_steps=spec.max_steps,
            max_new_tokens=self.parent_agent.max_new_tokens,
            depth=spec.depth,
            max_depth=spec.max_depth,
            read_only=spec.read_only,
            secret_env_names=self.parent_agent.secret_env_names,
            shell_env_allowlist=self.parent_agent.shell_env_allowlist,
        )

    @staticmethod
    def allowed_tools(agent):
        return tuple(sorted(name for name, tool in agent.tools.items() if not tool["risky"]))

    def worker_metadata(self, spec, extra=None):
        metadata = {
            "worker_id": spec.worker_id,
            "run_id": spec.run_id,
            "parent_run_id": spec.parent_run_id,
            "task": spec.task,
            "read_only": spec.read_only,
            "max_steps": spec.max_steps,
            "allowed_tools": list(spec.allowed_tools),
            "depth": spec.depth,
            "max_depth": spec.max_depth,
            "workspace_root": spec.workspace_root,
        }
        metadata.update(extra or {})
        return metadata

    def record_worker(self, spec, extra=None):
        task_state = getattr(self.parent_agent, "current_task_state", None)
        if task_state is None:
            return
        task_state.record_worker(self.worker_metadata(spec, extra))
        self.parent_agent.run_store.write_task_state(task_state)

    def emit_parent_trace(self, event, spec, extra=None):
        task_state = getattr(self.parent_agent, "current_task_state", None)
        if task_state is None:
            return None
        return self.parent_agent.emit_trace(task_state, event, self.worker_metadata(spec, extra))

    @staticmethod
    def _task(args):
        task = str((args or {}).get("task", "")).strip()
        if not task:
            raise ValueError("task must not be empty")
        return task
