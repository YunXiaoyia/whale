# Agent Harness v1 Overview

Agent Harness v1 is the control loop that turns one user request into a bounded sequence of model calls, tool calls, memory updates, and local audit artifacts.

The main runtime object is `Whale`. Its `ask()` method creates task state, builds prompts, requests model output, parses tool or final-answer responses, executes approved tools, and writes trace/report artifacts.

The task state records the current run id, request, status, attempts, tool steps, last tool, stop reason, final answer, checkpoint id, and resume status. This makes each run recoverable and reviewable without relying only on terminal output.

The harness keeps side effects behind explicit tools. Risky tools require approval policy checks, and file paths are constrained to the workspace root.
