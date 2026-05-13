"""Tool policy decisions for Whale runtime."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolPolicyDecision:
    tool_name: str
    allowed: bool
    tool_status: str = "pending"
    tool_error_code: str = ""
    security_event_type: str = ""
    risk_level: str = "low"
    read_only: bool = True
    message: str = ""
    affected_paths: tuple[str, ...] = field(default_factory=tuple)
    workspace_changed: bool = False
    diff_summary: tuple[str, ...] = field(default_factory=tuple)

    def metadata(self):
        return {
            "tool_status": self.tool_status,
            "tool_error_code": self.tool_error_code,
            "security_event_type": self.security_event_type,
            "risk_level": self.risk_level,
            "read_only": self.read_only,
            "affected_paths": list(self.affected_paths),
            "workspace_changed": self.workspace_changed,
            "diff_summary": list(self.diff_summary),
        }


class ToolPolicy:
    def evaluate(self, agent, name, args):
        tool = agent.tools.get(name)
        if tool is None:
            return ToolPolicyDecision(
                tool_name=name,
                allowed=False,
                tool_status="rejected",
                tool_error_code="unknown_tool",
                risk_level="high",
                read_only=False,
                message=f"error: unknown tool '{name}'",
            )
        try:
            agent.validate_tool(name, args)
        except Exception as exc:
            example = agent.tool_example(name)
            message = f"error: invalid arguments for {name}: {exc}"
            if example:
                message += f"\nexample: {example}"
            return ToolPolicyDecision(
                tool_name=name,
                allowed=False,
                tool_status="rejected",
                tool_error_code="invalid_arguments",
                security_event_type="path_escape" if "path escapes workspace" in str(exc) else "",
                risk_level=_risk_level(tool),
                read_only=_read_only(tool),
                message=message,
            )
        if agent.repeated_tool_call(name, args):
            return ToolPolicyDecision(
                tool_name=name,
                allowed=False,
                tool_status="rejected",
                tool_error_code="repeated_identical_call",
                risk_level=_risk_level(tool),
                read_only=_read_only(tool),
                message=f"error: repeated identical tool call for {name}; choose a different tool or return a final answer",
            )
        if tool["risky"] and not agent.approve(name, args):
            return ToolPolicyDecision(
                tool_name=name,
                allowed=False,
                tool_status="rejected",
                tool_error_code="approval_denied",
                security_event_type="read_only_block" if agent.read_only else "approval_denied",
                risk_level="high",
                read_only=False,
                message=f"error: approval denied for {name}",
            )
        return ToolPolicyDecision(
            tool_name=name,
            allowed=True,
            risk_level=_risk_level(tool),
            read_only=_read_only(tool),
        )


def _risk_level(tool):
    return "high" if tool["risky"] else "low"


def _read_only(tool):
    return not tool["risky"]
