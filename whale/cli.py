"""命令行入口。

这个模块负责把“用户怎么启动 whale”翻译成 runtime 能理解的对象：
解析参数、挑模型后端、构建工作区快照、恢复或新建 session，
最后进入 one-shot 或交互式循环。
"""

import argparse
import os
import shutil
import sys
import textwrap
import threading
import time

from .config import DEFAULT_PROVIDER_PROFILES, DEFAULT_WHALE_CONFIG, load_project_env, provider_env
from .models import AnthropicCompatibleModelClient, OllamaModelClient, OpenAICompatibleModelClient
from .runtime import Whale, SessionStore
from .workspace import WorkspaceContext, middle

DEFAULT_SECRET_ENV_NAMES = (
    "WHALE_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_API_TOKEN",
    "WHALE_ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "WHALE_DEEPSEEK_API_KEY",
    "DEEPSEEK_API_KEY",
    "WHALE_RIGHT_CODES_API_KEY",
    "RIGHT_CODES_API_KEY",
    "GITHUB_PAT",
    "GH_PAT",
)

WELCOME_ART = (
    "          .-''''-.",
    "     .--'  o    o '--.",
    "    /  ___        ___  \\__",
    "   |  /   \\______/   \\    )",
    "    \\_\\              /_..-'",
    "       '--._______.--'",
)
WELCOME_NAME = "whale"
WELCOME_SUBTITLE = "local coding agent"
WELCOME_STATUS = "calm shell, ready for work"
HELP_DETAILS = textwrap.dedent(
    """\
    Commands:
    /help    Show this help message.
    /memory  Show the agent's distilled working memory.
    /session Show the path to the saved session file.
    /reset   Clear the current session history and memory.
    /exit    Exit the agent.
    """
).strip()
SLASH_COMMANDS = ("/help", "/memory", "/session", "/reset", "/exit", "/quit")


class ThinkingStatusLine:
    def __init__(self, stream=None, interval=1.0, enabled=None):
        self.stream = stream or sys.stderr
        if enabled is None:
            enabled = bool(getattr(self.stream, "isatty", lambda: False)())
        self.enabled = bool(enabled)
        self.interval = float(interval)
        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = None
        self._label = ""
        self._started_at = 0.0
        self._render_width = 0
        self._active = False

    def __call__(self, message):
        if not self.enabled:
            return
        if message:
            self.start(str(message))
        else:
            self.stop()

    def start(self, label):
        with self._lock:
            if self._active:
                self._label = str(label)
                self._render(int(time.monotonic() - self._started_at))
                return
            self._active = True
            self._label = str(label)
            self._started_at = time.monotonic()
            self._stop_event = threading.Event()
            self._render(0)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            if not self._active:
                return
            stop_event = self._stop_event
            thread = self._thread
            self._active = False
            self._stop_event = None
            self._thread = None
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=max(self.interval * 2, 0.1))
        self._clear()

    def _run(self):
        while True:
            stop_event = self._stop_event
            if stop_event is None:
                return
            if stop_event.wait(self.interval):
                return
            self._render(int(time.monotonic() - self._started_at))

    def _render(self, elapsed):
        text = f"{self._label} {elapsed}s"
        width = max(self._render_width, len(text))
        self._render_width = width
        self._write("\r" + text.ljust(width))

    def _clear(self):
        if self._render_width:
            self._write("\r" + (" " * self._render_width) + "\r")
        else:
            self._write("\r")
        self._render_width = 0

    def _write(self, text):
        self.stream.write(text)
        flush = getattr(self.stream, "flush", None)
        if callable(flush):
            flush()


def split_repl_command(user_input):
    text = str(user_input or "").strip()
    if not text.startswith("/"):
        return "", ""
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return command, args


def slash_command_completer(text, state):
    needle = str(text or "")
    matches = [command for command in SLASH_COMMANDS if command.startswith(needle)]
    try:
        return matches[state]
    except IndexError:
        return None


def install_repl_completion():
    try:
        import readline
    except ImportError:
        return False

    def complete(text, state):
        buffer = readline.get_line_buffer()
        if buffer.lstrip() and not buffer.lstrip().startswith("/"):
            return None
        return slash_command_completer(text, state)

    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    return True


def handle_repl_command(agent, user_input):
    command, _args = split_repl_command(user_input)
    if not command:
        return False, False
    if command in {"/exit", "/quit"}:
        return True, True
    if command == "/help":
        print(HELP_DETAILS)
        return True, False
    if command == "/memory":
        print(agent.memory_text())
        return True, False
    if command == "/session":
        print(agent.session_path)
        return True, False
    if command == "/reset":
        agent.reset()
        print("session reset")
        return True, False

    print(f"unknown command: {command}. Type /help for available commands.")
    return True, False


DEFAULT_OLLAMA_MODEL = DEFAULT_PROVIDER_PROFILES["ollama"].default_model
DEFAULT_OLLAMA_HOST = DEFAULT_PROVIDER_PROFILES["ollama"].default_host
DEFAULT_OPENAI_MODEL = DEFAULT_PROVIDER_PROFILES["openai"].default_model
DEFAULT_OPENAI_BASE_URL = DEFAULT_PROVIDER_PROFILES["openai"].default_base_url
DEFAULT_ANTHROPIC_MODEL = DEFAULT_PROVIDER_PROFILES["anthropic"].default_model
DEFAULT_ANTHROPIC_BASE_URL = DEFAULT_PROVIDER_PROFILES["anthropic"].default_base_url
DEFAULT_DEEPSEEK_MODEL = DEFAULT_PROVIDER_PROFILES["deepseek"].default_model
DEFAULT_DEEPSEEK_BASE_URL = DEFAULT_PROVIDER_PROFILES["deepseek"].default_base_url
LEGACY_SECRET_ENV_NAMES_VAR = "WHALE_LEGACY_SECRET_ENV_NAMES"
SECRET_ENV_NAMES_VAR = "WHALE_SECRET_ENV_NAMES"


def _effective_model(args, provider):
    # 模型选择优先级：
    # 1. 用户显式传入 --model
    # 2. provider 对应的环境变量
    # 3. 代码里的默认值
    explicit_model = getattr(args, "model", None)
    if explicit_model:
        return explicit_model
    profile = DEFAULT_PROVIDER_PROFILES[provider]
    if profile.model_env:
        model = provider_env(profile.model_env, profile.model_legacy_env)
        if model:
            return model
    return profile.default_model


def _configured_secret_names(args):
    configured_secret_names = set(DEFAULT_SECRET_ENV_NAMES)
    configured_secret_names.update(str(name).upper() for name in args.secret_env_names)
    extra_names = os.environ.get(SECRET_ENV_NAMES_VAR, "")
    if not extra_names.strip():
        extra_names = os.environ.get(LEGACY_SECRET_ENV_NAMES_VAR, "")
    if extra_names.strip():
        configured_secret_names.update(
            item.strip().upper()
            for item in extra_names.split(",")
            if item.strip()
        )
    return sorted(configured_secret_names)


def _build_model_client(args):
    provider = getattr(args, "provider", "openai")
    profile = DEFAULT_PROVIDER_PROFILES[provider]
    # CLI 只负责把 provider 选择翻译成具体 client。
    # 真正的提示词格式、缓存支持、HTTP 协议差异，都封装在 models.py 里。
    if provider == "openai":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env(
            profile.base_url_env,
            profile.base_url_legacy_env,
            profile.default_base_url,
        )
        api_key = provider_env(profile.api_key_env, profile.api_key_legacy_env)
        return OpenAICompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )
    if provider == "anthropic":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env(
            profile.base_url_env,
            profile.base_url_legacy_env,
            profile.default_base_url,
        )
        api_key = provider_env(profile.api_key_env, profile.api_key_legacy_env)
        return AnthropicCompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )
    if provider == "deepseek":
        model = _effective_model(args, provider)
        base_url = getattr(args, "base_url", None) or provider_env(
            profile.base_url_env,
            profile.base_url_legacy_env,
            profile.default_base_url,
        )
        api_key = provider_env(profile.api_key_env, profile.api_key_legacy_env)
        return AnthropicCompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=args.temperature,
            timeout=getattr(args, "openai_timeout", getattr(args, "ollama_timeout", 300)),
        )

    model = _effective_model(args, provider)
    host = getattr(args, "host", profile.default_host)
    return OllamaModelClient(
        model=model,
        host=host,
        temperature=args.temperature,
        top_p=args.top_p,
        timeout=args.ollama_timeout,
    )


def build_welcome(agent, model, host):
    width = max(68, min(shutil.get_terminal_size((80, 20)).columns, 84))
    inner = width - 4
    gap = 3
    left_width = (inner - gap) // 2
    right_width = inner - gap - left_width

    def row(text):
        body = middle(text, width - 4)
        return f"| {body.ljust(width - 4)} |"

    def divider(char="-"):
        return "+" + char * (width - 2) + "+"

    def center(text):
        body = middle(text, inner)
        return f"| {body.center(inner)} |"

    def cell(label, value, size):
        body = middle(f"{label:<9} {value}", size)
        return body.ljust(size)

    def pair(left_label, left_value, right_label, right_value):
        left = cell(left_label, left_value, left_width)
        right = cell(right_label, right_value, right_width)
        return f"| {left}{' ' * gap}{right} |"

    line = divider("=")
    rows = [center(text) for text in WELCOME_ART]
    rows.extend(
        [
            center(WELCOME_NAME),
            center(WELCOME_SUBTITLE),
            center(WELCOME_STATUS),
            divider("-"),
            row(""),
            row("WORKSPACE  " + middle(agent.workspace.cwd, inner - 11)),
            pair("MODEL", model, "BRANCH", agent.workspace.branch),
            pair("APPROVAL", agent.approval_policy, "SESSION", agent.session["id"]),
            row(""),
        ]
    )
    return "\n".join([line, *rows, line])


def build_agent(args):
    """根据 CLI 参数装配出一个可运行的 Whale 实例。

    为什么存在：
    命令行参数只是字符串和开关，runtime 需要的是已经装配好的对象图：
    model client、workspace snapshot、session store、secret 配置等。
    这个函数负责把“启动参数”翻译成“agent 运行现场”。

    输入 / 输出：
    - 输入：`argparse` 解析后的 `args`
    - 输出：一个新的 `Whale`，或一个从旧 session 恢复出来的 `Whale`

    在 agent 链路里的位置：
    它是整个程序启动链路里最靠近 runtime 的装配点。`main()` 先调它，
    得到 agent 后，后面无论是 one-shot 还是 REPL 模式，都会落到 `ask()`。
    """
    # 这里是 CLI 到 runtime 的装配点：
    # 先采集工作区快照和加载项目级环境，再整理 secret 名单、模型后端和 session。
    workspace = WorkspaceContext.build(args.cwd)
    load_project_env(workspace.repo_root)
    configured_secret_names = _configured_secret_names(args)
    store = SessionStore(DEFAULT_WHALE_CONFIG.stores.session_root(workspace.repo_root))
    model = _build_model_client(args)
    session_id = args.resume
    if session_id == "latest":
        session_id = store.latest()
    if session_id:
        agent = Whale.from_session(
            model_client=model,
            workspace=workspace,
            session_store=store,
            session_id=session_id,
            approval_policy=args.approval,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            secret_env_names=configured_secret_names,
        )
    else:
        agent = Whale(
            model_client=model,
            workspace=workspace,
            session_store=store,
            approval_policy=args.approval,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            secret_env_names=configured_secret_names,
        )
    agent.status_callback = ThinkingStatusLine()
    return agent


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Minimal coding agent for Ollama, OpenAI-compatible, Anthropic-compatible, or DeepSeek models.",
    )
    parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt.")
    parser.add_argument("--cwd", default=".", help="Workspace directory.")
    parser.add_argument("--provider", choices=("ollama", "openai", "anthropic", "deepseek"), default="openai", help="Model backend to use.")
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override. Defaults to qwen3.5:4b for Ollama, WHALE_OPENAI_MODEL for openai, WHALE_ANTHROPIC_MODEL for anthropic, and WHALE_DEEPSEEK_MODEL for deepseek when set.",
    )
    parser.add_argument("--host", default=DEFAULT_OLLAMA_HOST, help="Ollama server URL.")
    parser.add_argument("--base-url", default=None, help="Provider API base URL for openai, anthropic, or deepseek.")
    parser.add_argument("--ollama-timeout", type=int, default=300, help="Ollama request timeout in seconds.")
    parser.add_argument("--openai-timeout", type=int, default=300, help="OpenAI-compatible request timeout in seconds.")
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
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature sent to Ollama.")
    parser.add_argument("--top-p", type=float, default=0.9, help="Top-p sampling value sent to Ollama.")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if not args.prompt and not sys.stdin.isatty():
        print(
            "error: interactive mode requires a TTY. Activate the Conda environment and run "
            "`whale ...`, or pass a prompt for one-shot mode.",
            file=sys.stderr,
        )
        return 2

    agent = build_agent(args)

    model = getattr(agent.model_client, "model", getattr(args, "model", DEFAULT_OLLAMA_MODEL))
    host = getattr(agent.model_client, "host", getattr(agent.model_client, "base_url", getattr(args, "host", DEFAULT_OLLAMA_HOST)))
    print(build_welcome(agent, model=model, host=host))

    if args.prompt:
        # one-shot 模式：只跑一次 ask，不进入 REPL 循环。
        prompt = " ".join(args.prompt).strip()
        if prompt:
            print()
            try:
                print(agent.ask(prompt))
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return 0

    install_repl_completion()
    while True:
        # 交互模式：每次读取一条用户输入，交给同一个 agent，
        # 因此 session history 和 working memory 会跨轮延续。
        try:
            user_input = input("\nwhale> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0

        if not user_input:
            continue
        handled, should_exit = handle_repl_command(agent, user_input)
        if should_exit:
            return 0
        if handled:
            continue

        print()
        try:
            print(agent.ask(user_input))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
