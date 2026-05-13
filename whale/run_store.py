"""运行工件落盘。

session.json 负责保存“可恢复的会话状态”；RunStore 负责保存“单次运行的审计工件”，
例如 task_state、trace 和 report。两者分开后，恢复现场和复盘证据不会混在一起。
"""

import json
import tempfile
from pathlib import Path


def _run_id(value):
    if hasattr(value, "run_id"):
        return value.run_id
    return str(value)


class RunStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id):
        return self.root / _run_id(run_id)

    def task_state_path(self, run_id):
        return self.run_dir(run_id) / "task_state.json"

    def trace_path(self, run_id):
        return self.run_dir(run_id) / "trace.jsonl"

    def report_path(self, run_id):
        return self.run_dir(run_id) / "report.json"

    def start_run(self, task_state):
        # 每次 ask() 都会生成一个 run 目录。
        # 这样一次用户请求对应一组独立工件，后续排查更容易。
        run_dir = self.run_dir(task_state)
        run_dir.mkdir(parents=True, exist_ok=True)
        self.write_task_state(task_state)
        return run_dir

    def write_task_state(self, task_state):
        path = self.task_state_path(task_state)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, task_state.to_dict())
        return path

    def append_trace(self, task_state, event):
        path = self.trace_path(task_state)
        path.parent.mkdir(parents=True, exist_ok=True)
        # trace 采用 jsonl 追加写入，原因是 agent 运行过程是流式事件序列，
        # 逐条落盘比“最后一次性写整份 trace”更稳，也更适合调试。
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
        return path

    def write_report(self, task_state, report):
        path = self.report_path(task_state)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, report)
        return path

    def load_task_state(self, task_id):
        return json.loads(self.task_state_path(task_id).read_text(encoding="utf-8"))

    def load_report(self, task_id):
        return json.loads(self.report_path(task_id).read_text(encoding="utf-8"))

    def list_runs(self, limit=None):
        if not self.root.exists():
            return []
        if limit is not None and int(limit) <= 0:
            return []

        summaries = []
        run_dirs = [path for path in self.root.iterdir() if path.is_dir()]
        for run_dir in sorted(run_dirs, key=lambda path: path.name, reverse=True):
            if not (run_dir / "task_state.json").exists() and not (run_dir / "report.json").exists():
                continue
            summaries.append(self.load_run_summary(run_dir.name))
            if limit is not None and len(summaries) >= int(limit):
                break
        return summaries

    def load_run_summary(self, run_id):
        run_id = _run_id(run_id)
        task_state = self._load_json_if_exists(self.task_state_path(run_id))
        report = self._load_json_if_exists(self.report_path(run_id))
        state = {}
        if isinstance(report, dict) and isinstance(report.get("task_state"), dict):
            state = report["task_state"]
        elif isinstance(task_state, dict):
            state = task_state
        report_source = report if isinstance(report, dict) else {}

        workers = state.get("workers", [])
        if not isinstance(workers, list):
            workers = []
        return {
            "run_id": str(report_source.get("run_id") or state.get("run_id") or run_id),
            "task_id": str(report_source.get("task_id") or state.get("task_id", "")),
            "user_request": str(state.get("user_request", "")),
            "status": str(report_source.get("status") or state.get("status", "")),
            "stop_reason": str(report_source.get("stop_reason") or state.get("stop_reason", "")),
            "final_answer": str(report_source.get("final_answer") or state.get("final_answer", "")),
            "tool_steps": int(report_source.get("tool_steps", state.get("tool_steps", 0)) or 0),
            "attempts": int(report_source.get("attempts", state.get("attempts", 0)) or 0),
            "checkpoint_id": str(report_source.get("checkpoint_id") or state.get("checkpoint_id", "")),
            "resume_status": str(report_source.get("resume_status") or state.get("resume_status", "")),
            "parent_run_id": str(state.get("parent_run_id", "")),
            "worker_id": str(state.get("worker_id", "")),
            "workers": workers,
            "has_task_state": task_state is not None,
            "has_report": report is not None,
            "has_trace": self.trace_path(run_id).exists(),
        }

    def _write_json_atomic(self, path, payload):
        # 原子写：先写临时文件，再 replace。
        # 这样即使中途异常，也不容易留下半截 JSON。
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_name = handle.name
        Path(temp_name).replace(path)

    @staticmethod
    def _load_json_if_exists(path):
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
