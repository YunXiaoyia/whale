from whale import FakeModelClient, SessionStore, WhaleAgent, WorkspaceContext
from whale.tool_policy import ToolPolicy


def build_agent(tmp_path, outputs=None, **kwargs):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    workspace = WorkspaceContext.build(tmp_path)
    store = SessionStore(tmp_path / ".whale" / "sessions")
    approval_policy = kwargs.pop("approval_policy", "auto")
    return WhaleAgent(
        model_client=FakeModelClient(outputs or []),
        workspace=workspace,
        session_store=store,
        approval_policy=approval_policy,
        **kwargs,
    )


def test_tool_policy_rejects_unknown_and_invalid_tools(tmp_path):
    agent = build_agent(tmp_path)
    policy = ToolPolicy()

    unknown = policy.evaluate(agent, "missing", {})
    invalid = policy.evaluate(agent, "read_file", {"path": "../outside.txt"})

    assert unknown.allowed is False
    assert unknown.tool_error_code == "unknown_tool"
    assert unknown.risk_level == "high"
    assert invalid.allowed is False
    assert invalid.tool_error_code == "invalid_arguments"
    assert invalid.security_event_type == "path_escape"
    assert "path escapes workspace" in invalid.message


def test_tool_policy_keeps_approval_and_read_only_decisions(tmp_path):
    agent = build_agent(tmp_path, approval_policy="never")
    policy = ToolPolicy()

    denied = policy.evaluate(agent, "run_shell", {"command": "echo hi", "timeout": 20})

    assert denied.allowed is False
    assert denied.tool_error_code == "approval_denied"
    assert denied.security_event_type == "approval_denied"
    assert denied.risk_level == "high"
    assert denied.read_only is False

    read_only_agent = build_agent(tmp_path / "child", approval_policy="auto", read_only=True)
    blocked = policy.evaluate(read_only_agent, "write_file", {"path": "x.txt", "content": "nope"})

    assert blocked.allowed is False
    assert blocked.tool_error_code == "approval_denied"
    assert blocked.security_event_type == "read_only_block"


def test_tool_policy_rejects_repeated_identical_calls(tmp_path):
    agent = build_agent(tmp_path)
    policy = ToolPolicy()
    tool_event = {
        "role": "tool",
        "name": "read_file",
        "args": {"path": "README.md", "start": 1, "end": 5},
        "content": "demo",
        "created_at": "2026-04-07T00:00:00+00:00",
    }
    agent.session["history"] = [dict(tool_event), dict(tool_event)]

    decision = policy.evaluate(agent, "read_file", {"path": "README.md", "start": 1, "end": 5})

    assert decision.allowed is False
    assert decision.tool_error_code == "repeated_identical_call"
    assert decision.risk_level == "low"
    assert decision.read_only is True


def test_tool_policy_allows_valid_safe_tool(tmp_path):
    agent = build_agent(tmp_path)
    decision = ToolPolicy().evaluate(agent, "read_file", {"path": "README.md", "start": 1, "end": 5})

    assert decision.allowed is True
    assert decision.risk_level == "low"
    assert decision.read_only is True
