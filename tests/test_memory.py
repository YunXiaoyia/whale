from whale.memory import LayeredMemory, memory_summary


def test_working_memory_tracks_summary_and_recent_files():
    memory = LayeredMemory()

    memory.set_task_summary("Investigate flaky tests")
    memory.remember_file("README.md")
    memory.remember_file("src/app.py")
    memory.remember_file("README.md")

    snapshot = memory.to_dict()

    assert snapshot["working"]["task_summary"] == "Investigate flaky tests"
    assert snapshot["working"]["recent_files"] == ["src/app.py", "README.md"]
    assert snapshot["task"] == "Investigate flaky tests"
    assert snapshot["files"] == ["src/app.py", "README.md"]


def test_episodic_notes_append_and_retrieve_deterministically():
    memory = LayeredMemory()

    memory.append_note("Exact tag note", tags=("recall",), created_at="2026-04-07T10:00:00+00:00")
    memory.append_note("Keyword overlap note about memory", created_at="2026-04-07T10:01:00+00:00")
    memory.append_note("Newest unrelated note", created_at="2026-04-07T10:02:00+00:00")
    memory.append_note("Older unrelated note", created_at="2026-04-07T09:59:00+00:00")

    snapshot = memory.to_dict()
    assert [note["text"] for note in snapshot["episodic_notes"]] == [
        "Exact tag note",
        "Keyword overlap note about memory",
        "Newest unrelated note",
        "Older unrelated note",
    ]
    assert snapshot["notes"] == [
        "Exact tag note",
        "Keyword overlap note about memory",
        "Newest unrelated note",
        "Older unrelated note",
    ]

    lines = [line for line in memory.retrieval_view("recall memory", limit=4).splitlines() if line.startswith("- ")]
    assert lines == [
        "- Exact tag note",
        "- Keyword overlap note about memory",
    ]


def test_file_summaries_use_canonical_paths_and_freshness(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\n", encoding="utf-8")
    memory = LayeredMemory(workspace_root=tmp_path)

    memory.set_file_summary("./sample.txt", "sample.txt: alpha")
    memory.remember_file("./sample.txt")
    snapshot = memory.to_dict()["file_summaries"]["sample.txt"]

    assert snapshot["summary"] == "sample.txt: alpha"
    assert snapshot["freshness"]

    assert "sample.txt: alpha" in memory.render_memory_text()
    file_path.write_text("beta\n", encoding="utf-8")
    assert "sample.txt: alpha" not in memory.render_memory_text()

    memory.invalidate_file_summary("sample.txt")

    assert "sample.txt" not in memory.to_dict()["file_summaries"]


def test_process_notes_keep_kind_and_latest_duplicate_wins():
    memory = LayeredMemory()

    memory.append_note(
        "Shell partial success on README.md; inspect diff before retry",
        tags=("process", "partial_success"),
        created_at="2026-04-07T10:00:00+00:00",
        kind="process",
    )
    memory.append_note(
        "Shell partial success on README.md; inspect diff before retry",
        tags=("process", "partial_success"),
        created_at="2026-04-07T10:01:00+00:00",
        kind="process",
    )

    notes = memory.to_dict()["episodic_notes"]

    assert len(notes) == 1
    assert notes[0]["kind"] == "process"
    assert notes[0]["created_at"] == "2026-04-07T10:01:00+00:00"


def test_durable_memory_index_and_topic_notes_are_loaded_and_retrieved(tmp_path):
    memory_root = tmp_path / ".whale" / "memory"
    topics_dir = memory_root / "topics"
    topics_dir.mkdir(parents=True)
    (memory_root / "MEMORY.md").write_text(
        "# Durable Memory Index\n\n"
        "- [project-conventions](topics/project-conventions.md): Project Conventions\n"
        "  - summary: Stable repository conventions.\n"
        "  - tags: convention\n",
        encoding="utf-8",
    )
    (topics_dir / "project-conventions.md").write_text(
        "# Project Conventions\n\n"
        "- topic: project-conventions\n"
        "- summary: Stable repository conventions.\n"
        "- tags: convention\n"
        "- updated_at: 2026-04-12T08:14:49+00:00\n\n"
        "## Notes\n"
        "- Use constrained tools instead of guessing.\n"
        "- Preserve local agent state under .whale/.\n",
        encoding="utf-8",
    )

    memory = LayeredMemory(workspace_root=tmp_path)

    snapshot = memory.to_dict()
    assert snapshot["durable_topics"] == ["project-conventions"]

    lines = [line for line in memory.retrieval_view("constrained tools", limit=4).splitlines() if line.startswith("- ")]
    assert any("Use constrained tools instead of guessing." in line for line in lines)


def test_memory_summary_reports_lifecycle_counts_and_limits(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("alpha\n", encoding="utf-8")
    memory = LayeredMemory(workspace_root=tmp_path)

    memory.set_task_summary("Investigate memory lifecycle")
    memory.remember_file("sample.txt")
    memory.set_file_summary("sample.txt", "sample.txt: alpha")
    memory.append_note("read sample.txt", tags=("sample.txt",), source="sample.txt")
    memory.append_note("run_shell rejected; choose another action", kind="process")

    summary = memory_summary(
        memory.to_dict(),
        workspace_root=tmp_path,
        stale_summary_invalidations=2,
        durable_promotions=("project-conventions: Use constrained tools.",),
        durable_rejections=("dependency-facts:secret_shaped",),
    )

    assert summary["working_task_present"] is True
    assert summary["working_file_count"] == 1
    assert summary["working_file_limit"] == 8
    assert summary["recent_files"] == ["sample.txt"]
    assert summary["file_summary_count"] == 1
    assert summary["fresh_file_summary_count"] == 1
    assert summary["stale_file_summary_count"] == 0
    assert summary["episodic_note_count"] == 2
    assert summary["process_note_count"] == 1
    assert summary["stale_summary_invalidations"] == 2
    assert summary["durable_promotion_count"] == 1
    assert summary["durable_rejection_count"] == 1
