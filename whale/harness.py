"""Public harness APIs for wrapping Whale runtime and evaluation flows."""

from dataclasses import asdict, dataclass
from pathlib import Path

from .evaluator import (
    DEFAULT_BENCHMARK_PATH,
    DEFAULT_HARNESS_REGRESSION_V2_ARTIFACT_PATH,
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_VERSION,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEZONE,
    DEFAULT_TOP_P,
    BenchmarkEvaluator,
    run_harness_regression_v2,
)


HARNESS_SCHEMA_VERSION = 1


def _json_path(path, workspace_root):
    path = Path(path)
    root = Path(workspace_root)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


@dataclass(frozen=True)
class HarnessRunResult:
    schema_version: int
    answer: str
    run_id: str
    task_id: str
    status: str
    stop_reason: str
    tool_steps: int
    attempts: int
    run_dir: str
    task_state_path: str
    trace_path: str
    report_path: str

    def to_dict(self):
        return asdict(self)


class RuntimeHarness:
    """Thin public wrapper around an already constructed Whale instance."""

    def __init__(self, agent):
        self.agent = agent

    def run(self, prompt, run_id=None):
        answer = self.agent.ask(prompt, run_id=run_id)
        task_state = getattr(self.agent, "current_task_state", None)
        actual_run_id = str(getattr(task_state, "run_id", "") or run_id or "")
        if not actual_run_id:
            raise RuntimeError("Whale.ask() finished without exposing a run id.")

        store = self.agent.run_store
        summary = store.load_run_summary(actual_run_id)
        workspace_root = getattr(self.agent, "root", Path.cwd())
        return HarnessRunResult(
            schema_version=HARNESS_SCHEMA_VERSION,
            answer=str(answer if answer is not None else summary.get("final_answer", "")),
            run_id=str(summary.get("run_id") or actual_run_id),
            task_id=str(summary.get("task_id", "")),
            status=str(summary.get("status", "")),
            stop_reason=str(summary.get("stop_reason", "")),
            tool_steps=int(summary.get("tool_steps", 0) or 0),
            attempts=int(summary.get("attempts", 0) or 0),
            run_dir=_json_path(store.run_dir(actual_run_id), workspace_root),
            task_state_path=_json_path(store.task_state_path(actual_run_id), workspace_root),
            trace_path=_json_path(store.trace_path(actual_run_id), workspace_root),
            report_path=_json_path(store.report_path(actual_run_id), workspace_root),
        )


class EvaluationHarness:
    """Thin public wrapper around the deterministic benchmark evaluator."""

    def __init__(
        self,
        benchmark_path=DEFAULT_BENCHMARK_PATH,
        artifact_path=DEFAULT_HARNESS_REGRESSION_V2_ARTIFACT_PATH,
        workspace_root=None,
        model_name=DEFAULT_MODEL_NAME,
        model_version=DEFAULT_MODEL_VERSION,
        temperature=DEFAULT_TEMPERATURE,
        top_p=DEFAULT_TOP_P,
        max_new_tokens=DEFAULT_MAX_NEW_TOKENS,
        timezone_name=DEFAULT_TIMEZONE,
        model_client_factory=None,
    ):
        self.benchmark_path = Path(benchmark_path)
        self.artifact_path = Path(artifact_path)
        self.workspace_root = Path(workspace_root) if workspace_root is not None else None
        self.model_name = model_name
        self.model_version = model_version
        self.temperature = temperature
        self.top_p = top_p
        self.max_new_tokens = max_new_tokens
        self.timezone_name = timezone_name
        self.model_client_factory = model_client_factory

    def build_evaluator(self):
        return BenchmarkEvaluator(
            benchmark_path=self.benchmark_path,
            artifact_path=self.artifact_path,
            workspace_root=self.workspace_root,
            model_name=self.model_name,
            model_version=self.model_version,
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_new_tokens,
            timezone_name=self.timezone_name,
            model_client_factory=self.model_client_factory,
        )

    def run(self):
        return run_harness_regression_v2(
            benchmark_path=self.benchmark_path,
            artifact_path=self.artifact_path,
            workspace_root=self.workspace_root,
            model_name=self.model_name,
            model_version=self.model_version,
            temperature=self.temperature,
            top_p=self.top_p,
            max_new_tokens=self.max_new_tokens,
            timezone_name=self.timezone_name,
            model_client_factory=self.model_client_factory,
        )
