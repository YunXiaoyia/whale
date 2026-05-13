"""Project-local configuration helpers and internal config objects."""

from dataclasses import dataclass, field
import os
import re
from pathlib import Path


ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_CONTEXT_SECTION_BUDGETS = {
    "prefix": 3600,
    "memory": 1600,
    "relevant_memory": 1200,
    "history": 5200,
}
DEFAULT_CONTEXT_SECTION_FLOORS = {
    "prefix": 1200,
    "memory": 400,
    "relevant_memory": 300,
    "history": 1500,
}
DEFAULT_CONTEXT_REDUCTION_ORDER = ("relevant_memory", "history", "memory", "prefix")
DEFAULT_SHELL_ENV_ALLOWLIST = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LOGNAME",
    "PATH",
    "PWD",
    "SHELL",
    "TERM",
    "TMPDIR",
    "TMP",
    "TEMP",
    "USER",
)
DEFAULT_FEATURE_FLAGS = {
    "memory": True,
    "relevant_memory": True,
    "context_reduction": True,
    "prompt_cache": True,
}


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    client_type: str
    default_model: str
    default_base_url: str = ""
    default_host: str = ""
    model_env: str = ""
    model_legacy_env: tuple[str, ...] = ()
    base_url_env: str = ""
    base_url_legacy_env: tuple[str, ...] = ()
    api_key_env: str = ""
    api_key_legacy_env: tuple[str, ...] = ()
    default_temperature: float | None = 0.2
    default_top_p: float | None = None
    default_timeout: int = 300
    supports_prompt_cache: bool = False


@dataclass(frozen=True)
class RuntimeConfig:
    max_steps: int = 6
    max_new_tokens: int = 512
    feature_flags: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_FEATURE_FLAGS))


@dataclass(frozen=True)
class ContextConfig:
    name: str = "default"
    budget_profile: str = "standard"
    total_budget: int = 12000
    section_budgets: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CONTEXT_SECTION_BUDGETS))
    section_floors: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CONTEXT_SECTION_FLOORS))
    reduction_order: tuple[str, ...] = DEFAULT_CONTEXT_REDUCTION_ORDER
    relevant_memory_limit: int = 3
    skill_instruction_budget: int = 1200
    context_reduction_enabled: bool = True


@dataclass(frozen=True)
class ToolConfig:
    approval_policy: str = "ask"
    shell_env_allowlist: tuple[str, ...] = DEFAULT_SHELL_ENV_ALLOWLIST
    default_shell_timeout: int = 20
    shell_timeout_min: int = 1
    shell_timeout_max: int = 120
    max_output_chars: int = 4000
    risky_tools: tuple[str, ...] = ("run_shell", "write_file", "patch_file")
    low_risk_tools: tuple[str, ...] = ("list_files", "read_file", "search", "delegate")
    repeat_call_policy: str = "reject-identical-recent"


@dataclass(frozen=True)
class WorkerConfig:
    enabled: bool = True
    max_depth: int = 1
    default_max_steps: int = 3
    read_only: bool = True


@dataclass(frozen=True)
class MemoryConfig:
    enabled: bool = True
    relevant_memory_enabled: bool = True
    working_file_limit: int = 8
    episodic_note_limit: int = 12
    file_summary_limit: int = 6
    relevant_memory_limit: int = 3
    task_summary_chars: int = 300
    note_chars: int = 500
    file_summary_chars: int = 500
    read_summary_chars: int = 180
    freshness_invalidation_enabled: bool = True
    durable_topic_allowlist: tuple[str, ...] = (
        "project-conventions",
        "key-decisions",
        "dependency-facts",
        "user-preferences",
    )


@dataclass(frozen=True)
class StoreConfig:
    whale_dir: str = ".whale"
    sessions_dir: str = "sessions"
    runs_dir: str = "runs"
    memory_dir: str = "memory"

    def whale_root(self, workspace_root):
        return Path(workspace_root) / self.whale_dir

    def session_root(self, workspace_root):
        return self.whale_root(workspace_root) / self.sessions_dir

    def run_root(self, workspace_root):
        return self.whale_root(workspace_root) / self.runs_dir

    def memory_root(self, workspace_root):
        return self.whale_root(workspace_root) / self.memory_dir


def default_provider_profiles():
    return {
        "ollama": ProviderProfile(
            name="ollama",
            client_type="ollama",
            default_model="qwen3.5:4b",
            default_host="http://127.0.0.1:11434",
            default_top_p=0.9,
            supports_prompt_cache=False,
        ),
        "openai": ProviderProfile(
            name="openai",
            client_type="openai-compatible",
            default_model="gpt-5.4",
            default_base_url="https://www.right.codes/codex/v1",
            model_env="WHALE_OPENAI_MODEL",
            model_legacy_env=("OPENAI_MODEL",),
            base_url_env="WHALE_OPENAI_API_BASE",
            base_url_legacy_env=("OPENAI_API_BASE",),
            api_key_env="WHALE_OPENAI_API_KEY",
            api_key_legacy_env=("OPENAI_API_KEY",),
            supports_prompt_cache=True,
        ),
        "anthropic": ProviderProfile(
            name="anthropic",
            client_type="anthropic-compatible",
            default_model="claude-sonnet-4-6",
            default_base_url="https://www.right.codes/claude/v1",
            model_env="WHALE_ANTHROPIC_MODEL",
            model_legacy_env=("ANTHROPIC_MODEL",),
            base_url_env="WHALE_ANTHROPIC_API_BASE",
            base_url_legacy_env=("ANTHROPIC_API_BASE",),
            api_key_env="WHALE_ANTHROPIC_API_KEY",
            api_key_legacy_env=(
                "ANTHROPIC_API_KEY",
                "WHALE_RIGHT_CODES_API_KEY",
                "RIGHT_CODES_API_KEY",
                "WHALE_OPENAI_API_KEY",
                "OPENAI_API_KEY",
            ),
        ),
        "deepseek": ProviderProfile(
            name="deepseek",
            client_type="anthropic-compatible",
            default_model="deepseek-v4-pro",
            default_base_url="https://api.deepseek.com/anthropic",
            model_env="WHALE_DEEPSEEK_MODEL",
            model_legacy_env=("DEEPSEEK_MODEL",),
            base_url_env="WHALE_DEEPSEEK_API_BASE",
            base_url_legacy_env=("DEEPSEEK_API_BASE",),
            api_key_env="WHALE_DEEPSEEK_API_KEY",
            api_key_legacy_env=("DEEPSEEK_API_KEY",),
        ),
    }


@dataclass(frozen=True)
class WhaleConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    provider_profiles: dict[str, ProviderProfile] = field(default_factory=default_provider_profiles)
    context: ContextConfig = field(default_factory=ContextConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    workers: WorkerConfig = field(default_factory=WorkerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    stores: StoreConfig = field(default_factory=StoreConfig)


DEFAULT_PROVIDER_PROFILES = default_provider_profiles()
DEFAULT_RUNTIME_CONFIG = RuntimeConfig()
DEFAULT_CONTEXT_CONFIG = ContextConfig()
DEFAULT_TOOL_CONFIG = ToolConfig()
DEFAULT_WORKER_CONFIG = WorkerConfig()
DEFAULT_MEMORY_CONFIG = MemoryConfig()
DEFAULT_STORE_CONFIG = StoreConfig()
DEFAULT_WHALE_CONFIG = WhaleConfig()


def _strip_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_env_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export "):].strip()
    if "=" not in line:
        raise ValueError(f"invalid .env line: {line}")
    name, value = line.split("=", 1)
    name = name.strip()
    if not ENV_KEY_PATTERN.match(name):
        raise ValueError(f"invalid .env variable name: {name}")
    return name, _strip_quotes(value)


def find_project_env(start):
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for path in (current, *current.parents):
        env_path = path / ".env"
        if env_path.exists():
            return env_path
    return None


def load_project_env(start, override=True):
    env_path = find_project_env(start)
    if env_path is None:
        return {}
    loaded = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        name, value = parsed
        loaded[name] = value
        if override or name not in os.environ:
            os.environ[name] = value
    return loaded


def provider_env(name, legacy_names=(), default=""):
    for env_name in (name, *legacy_names):
        value = os.environ.get(env_name)
        if value:
            return value
    return default
