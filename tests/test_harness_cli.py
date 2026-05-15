import json

from whale import FakeModelClient, SessionStore, Whale, WorkspaceContext
from whale import harness_cli


def build_agent(tmp_path, outputs):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return Whale(
        model_client=FakeModelClient(outputs),
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".whale" / "sessions"),
        approval_policy="auto",
    )


def test_harness_cli_run_prints_runtime_summary_json(tmp_path, monkeypatch, capsys):
    def fake_build_agent(args):
        assert args.cwd == str(tmp_path)
        assert args.approval == "auto"
        return build_agent(tmp_path, ["<final>Done.</final>"])

    monkeypatch.setattr(harness_cli, "build_agent", fake_build_agent)

    exit_code = harness_cli.main(
        [
            "run",
            "--cwd",
            str(tmp_path),
            "--approval",
            "auto",
            "--run-id",
            "run_cli_001",
            "Inspect",
            "the",
            "repo",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == 1
    assert payload["answer"] == "Done."
    assert payload["run_id"] == "run_cli_001"
    assert payload["status"] == "completed"
    assert payload["report_path"] == ".whale/runs/run_cli_001/report.json"


def test_harness_cli_eval_runs_regression_and_prints_artifact_json(tmp_path, monkeypatch, capsys):
    calls = {}

    class FakeEvaluationHarness:
        def __init__(self, **kwargs):
            calls.update(kwargs)

        def run(self):
            artifact_path = calls["artifact_path"]
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact = {
                "schema_version": 1,
                "summary": {"total_tasks": 0, "passed": 0, "failed": 0},
                "rows": [],
            }
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
            return artifact

    artifact_path = tmp_path / "artifacts" / "harness-regression-v2.json"
    workspace_root = tmp_path / "workspaces"
    monkeypatch.setattr(harness_cli, "EvaluationHarness", FakeEvaluationHarness)

    exit_code = harness_cli.main(
        [
            "eval",
            "--artifact-path",
            str(artifact_path),
            "--workspace-root",
            str(workspace_root),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == 1
    assert artifact_path.exists()
    assert calls["artifact_path"] == artifact_path
    assert calls["workspace_root"] == workspace_root
