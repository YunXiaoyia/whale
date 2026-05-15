import json

from whale import (
    EvaluationHarness,
    FakeModelClient,
    HarnessRunResult,
    RuntimeHarness,
    SessionStore,
    Whale,
    WorkspaceContext,
)
from whale.evaluator import BenchmarkEvaluator
import whale.harness as harness_module


def build_agent(tmp_path, outputs, **kwargs):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    workspace = WorkspaceContext.build(tmp_path)
    return Whale(
        model_client=FakeModelClient(outputs),
        workspace=workspace,
        session_store=SessionStore(tmp_path / ".whale" / "sessions"),
        approval_policy="auto",
        **kwargs,
    )


def test_runtime_harness_returns_json_ready_run_summary(tmp_path):
    agent = build_agent(tmp_path, ["<final>Done.</final>"])
    harness = RuntimeHarness(agent)

    result = harness.run("Inspect the repo.", run_id="run_harness_001")
    payload = result.to_dict()

    assert isinstance(result, HarnessRunResult)
    assert json.loads(json.dumps(payload)) == payload
    assert payload == {
        "schema_version": 1,
        "answer": "Done.",
        "run_id": "run_harness_001",
        "task_id": agent.current_task_state.task_id,
        "status": "completed",
        "stop_reason": "final_answer_returned",
        "tool_steps": 0,
        "attempts": 1,
        "run_dir": ".whale/runs/run_harness_001",
        "task_state_path": ".whale/runs/run_harness_001/task_state.json",
        "trace_path": ".whale/runs/run_harness_001/trace.jsonl",
        "report_path": ".whale/runs/run_harness_001/report.json",
    }
    assert (tmp_path / payload["task_state_path"]).exists()
    assert (tmp_path / payload["trace_path"]).exists()
    assert (tmp_path / payload["report_path"]).exists()


def test_runtime_harness_reads_summary_counts_from_run_store(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"hello.txt","start":1,"end":1}}</tool>',
            "<final>Read it.</final>",
        ],
    )

    result = RuntimeHarness(agent).run("Read hello.txt")
    payload = result.to_dict()
    trace_events = [
        json.loads(line)
        for line in (tmp_path / payload["trace_path"]).read_text(encoding="utf-8").splitlines()
    ]

    assert payload["answer"] == "Read it."
    assert payload["tool_steps"] == 1
    assert payload["attempts"] == 2
    assert payload["status"] == "completed"
    assert any(event["event"] == "tool_executed" for event in trace_events)


def test_evaluation_harness_builds_configured_benchmark_evaluator(tmp_path):
    harness = EvaluationHarness(
        artifact_path=tmp_path / "artifacts" / "harness-regression-v2.json",
        workspace_root=tmp_path / "workspaces",
        max_new_tokens=32,
    )

    evaluator = harness.build_evaluator()

    assert isinstance(evaluator, BenchmarkEvaluator)
    assert evaluator.benchmark_path == harness_module.DEFAULT_BENCHMARK_PATH
    assert evaluator.artifact_path == tmp_path / "artifacts" / "harness-regression-v2.json"
    assert evaluator.workspace_root == tmp_path / "workspaces"
    assert evaluator.max_new_tokens == 32


def test_evaluation_harness_runs_harness_regression_v2_with_default_artifact(monkeypatch):
    calls = {}

    def fake_regression(**kwargs):
        calls.update(kwargs)
        return {
            "schema_version": 1,
            "summary": {"total_tasks": 0, "passed": 0, "failed": 0},
            "rows": [],
        }

    monkeypatch.setattr(harness_module, "run_harness_regression_v2", fake_regression)

    artifact = EvaluationHarness().run()

    assert artifact["schema_version"] == 1
    assert calls["benchmark_path"] == harness_module.DEFAULT_BENCHMARK_PATH
    assert calls["artifact_path"] == harness_module.DEFAULT_HARNESS_REGRESSION_V2_ARTIFACT_PATH
    assert calls["workspace_root"] is None
