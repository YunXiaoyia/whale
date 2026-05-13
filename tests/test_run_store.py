import json

from whale.run_store import RunStore
from whale.task_state import STOP_REASON_FINAL_ANSWER_RETURNED, TaskState


def test_run_store_creates_run_directory_and_state_file(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    state = TaskState.create(run_id="run_001", task_id="task_001", user_request="Inspect the repo.")

    run_dir = store.start_run(state)

    assert run_dir == store.run_dir(state.run_id)
    assert run_dir.exists()
    persisted = json.loads((run_dir / "task_state.json").read_text(encoding="utf-8"))
    assert persisted["task_id"] == "task_001"
    assert persisted["run_id"] == "run_001"
    assert persisted["user_request"] == "Inspect the repo."


def test_run_store_appends_trace_jsonl(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    state = TaskState.create(run_id="run_002", task_id="task_002", user_request="Trace the run.")
    store.start_run(state)

    store.append_trace(state, {"event": "run_started", "created_at": "2026-04-07T00:00:00+00:00"})
    store.append_trace(
        state.run_id,
        {
            "event": "prompt_built",
            "created_at": "2026-04-07T00:00:01+00:00",
            "prompt_metadata": {"prompt_chars": 128, "secret_env_count": 1},
        },
    )
    store.append_trace(state.run_id, {"event": "run_finished", "created_at": "2026-04-07T00:00:02+00:00"})

    lines = (store.trace_path(state.run_id)).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["event"] == "run_started"
    assert json.loads(lines[1])["event"] == "prompt_built"
    assert json.loads(lines[2])["event"] == "run_finished"


def test_run_store_writes_report_json(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    state = TaskState.create(run_id="run_003", task_id="task_003", user_request="Report the run.")
    store.start_run(state)
    state.finish_success("Done.")

    store.write_task_state(state)
    store.write_report(state, {"task_state": state.to_dict(), "stop_reason": state.stop_reason})

    report = json.loads(store.report_path(state.run_id).read_text(encoding="utf-8"))
    assert report["stop_reason"] == STOP_REASON_FINAL_ANSWER_RETURNED
    assert report["task_state"]["final_answer"] == "Done."


def test_run_store_tolerates_missing_final_report(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    state = TaskState.create(run_id="run_004", task_id="task_004", user_request="Crash before finalize.")

    store.start_run(state)
    store.append_trace(state, {"event": "run_started"})

    assert store.trace_path(state.run_id).exists()
    assert not store.report_path(state.run_id).exists()


def test_run_store_lists_runs_without_requiring_reports(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    older = TaskState.create(run_id="run_20260407-100000-aaaaaa", task_id="task_older", user_request="Older run.")
    newer = TaskState.create(run_id="run_20260407-100001-bbbbbb", task_id="task_newer", user_request="Newer run.")
    newer.record_tool("read_file")
    newer.finish_success("Done.")

    store.start_run(older)
    store.start_run(newer)
    store.append_trace(newer, {"event": "run_started"})
    store.write_task_state(newer)
    store.write_report(newer, {"task_state": newer.to_dict(), "stop_reason": newer.stop_reason})

    summaries = store.list_runs()

    assert [item["run_id"] for item in summaries] == [newer.run_id, older.run_id]
    assert summaries[0]["has_report"] is True
    assert summaries[0]["has_trace"] is True
    assert summaries[0]["tool_steps"] == 1
    assert summaries[0]["stop_reason"] == STOP_REASON_FINAL_ANSWER_RETURNED
    assert summaries[1]["has_report"] is False
    assert summaries[1]["user_request"] == "Older run."


def test_run_store_loads_worker_run_summary_links(tmp_path):
    store = RunStore(tmp_path / ".whale" / "runs")
    parent = TaskState.create(run_id="run_parent", task_id="task_parent", user_request="Parent.")
    child = TaskState.create(run_id="run_child", task_id="task_child", user_request="Child.")
    child.parent_run_id = parent.run_id
    child.worker_id = "worker_001"
    parent.record_worker(
        {
            "worker_id": child.worker_id,
            "run_id": child.run_id,
            "parent_run_id": parent.run_id,
            "status": "completed",
        }
    )

    store.start_run(parent)
    store.write_task_state(parent)
    store.start_run(child)
    store.write_task_state(child)

    parent_summary = store.load_run_summary(parent.run_id)
    child_summary = store.load_run_summary(child.run_id)

    assert parent_summary["workers"][0]["run_id"] == child.run_id
    assert child_summary["parent_run_id"] == parent.run_id
    assert child_summary["worker_id"] == "worker_001"
