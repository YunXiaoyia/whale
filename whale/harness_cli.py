"""CLI entrypoint for Whale harness APIs."""

import argparse
import json
import sys
from pathlib import Path

from .cli import build_agent
from .config import DEFAULT_PROVIDER_PROFILES
from .evaluator import (
    DEFAULT_BENCHMARK_PATH,
    DEFAULT_HARNESS_REGRESSION_V2_ARTIFACT_PATH,
    DEFAULT_MAX_NEW_TOKENS,
)
from .harness import EvaluationHarness, RuntimeHarness


def _add_runtime_options(parser):
    parser.add_argument("--cwd", default=".", help="Workspace directory.")
    parser.add_argument(
        "--provider",
        choices=tuple(DEFAULT_PROVIDER_PROFILES),
        default="openai",
        help="Model backend to use.",
    )
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--host", default=DEFAULT_PROVIDER_PROFILES["ollama"].default_host, help="Ollama server URL.")
    parser.add_argument("--base-url", default=None, help="Provider API base URL for hosted providers.")
    parser.add_argument("--ollama-timeout", type=int, default=300, help="Ollama request timeout in seconds.")
    parser.add_argument("--openai-timeout", type=int, default=300, help="Hosted provider request timeout in seconds.")
    parser.add_argument("--resume", default=None, help="Session id to resume or 'latest'.")
    parser.add_argument("--approval", choices=("ask", "auto", "never"), default="ask", help="Approval policy for risky tools.")
    parser.add_argument(
        "--secret-env-name",
        dest="secret_env_names",
        action="append",
        default=[],
        help="Extra environment variable names to treat as secrets for trace/report redaction.",
    )
    parser.add_argument("--max-steps", type=int, default=6, help="Maximum tool/model iterations per request.")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Maximum model output tokens per step.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, default=0.9, help="Top-p sampling value.")


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Run Whale runtime and evaluation harnesses.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one prompt and print a runtime harness JSON summary.")
    _add_runtime_options(run_parser)
    run_parser.add_argument("--run-id", default=None, help="Optional run id override.")
    run_parser.add_argument("prompt", nargs="+", help="Prompt to run.")

    eval_parser = subparsers.add_parser("eval", help="Run deterministic harness regression and print the artifact JSON.")
    eval_parser.add_argument("--benchmark-path", type=Path, default=DEFAULT_BENCHMARK_PATH, help="Benchmark JSON path.")
    eval_parser.add_argument(
        "--artifact-path",
        type=Path,
        default=DEFAULT_HARNESS_REGRESSION_V2_ARTIFACT_PATH,
        help="Regression artifact output path.",
    )
    eval_parser.add_argument("--workspace-root", type=Path, default=None, help="Directory for benchmark workspace copies.")
    eval_parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=DEFAULT_MAX_NEW_TOKENS,
        help="Maximum model output tokens per benchmark step.",
    )
    return parser


def _write_json(payload, stream):
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")


def _run_command(args):
    agent = build_agent(args)
    prompt = " ".join(args.prompt).strip()
    result = RuntimeHarness(agent).run(prompt, run_id=args.run_id)
    _write_json(result.to_dict(), sys.stdout)
    return 0


def _eval_command(args):
    artifact = EvaluationHarness(
        benchmark_path=args.benchmark_path,
        artifact_path=args.artifact_path,
        workspace_root=args.workspace_root,
        max_new_tokens=args.max_new_tokens,
    ).run()
    _write_json(artifact, sys.stdout)
    return 0


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run_command(args)
        if args.command == "eval":
            return _eval_command(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
