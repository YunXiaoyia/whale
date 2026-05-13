import os
from unittest.mock import patch

from whale import FakeModelClient, SessionStore, WhaleAgent, WorkspaceContext
from whale import cli as whale_cli
from whale.config import ContextConfig, DEFAULT_WHALE_CONFIG, RuntimeConfig, ToolConfig, WhaleConfig, WorkerConfig


def test_whale_config_exposes_expected_internal_defaults():
    config = WhaleConfig()

    assert config.provider_profiles["openai"].default_model == "gpt-5.4"
    assert config.provider_profiles["deepseek"].client_type == "anthropic-compatible"
    assert config.context.total_budget == 12000
    assert config.context.section_budgets["history"] == 5200
    assert config.tools.shell_env_allowlist == DEFAULT_WHALE_CONFIG.tools.shell_env_allowlist
    assert config.workers.max_depth == 1
    assert config.memory.working_file_limit == 8
    assert config.stores.run_root("/repo").as_posix() == "/repo/.whale/runs"


def test_runtime_uses_internal_config_defaults_without_changing_public_defaults(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    workspace = WorkspaceContext.build(tmp_path)
    store = SessionStore(tmp_path / ".whale" / "sessions")

    agent = WhaleAgent(
        model_client=FakeModelClient(["<final>Done.</final>"]),
        workspace=workspace,
        session_store=store,
        config=WhaleConfig(),
    )

    assert agent.approval_policy == "ask"
    assert agent.max_steps == 6
    assert agent.max_new_tokens == 512
    assert agent.max_depth == 1
    assert agent.shell_env_allowlist == DEFAULT_WHALE_CONFIG.tools.shell_env_allowlist
    assert agent.run_store.root == tmp_path / ".whale" / "runs"
    assert agent.context_manager.total_budget == DEFAULT_WHALE_CONFIG.context.total_budget
    assert agent.context_manager.relevant_memory_limit == DEFAULT_WHALE_CONFIG.context.relevant_memory_limit


def test_runtime_accepts_internal_config_overrides(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    workspace = WorkspaceContext.build(tmp_path)
    store = SessionStore(tmp_path / ".whale" / "sessions")
    config = WhaleConfig(
        runtime=RuntimeConfig(max_steps=4, max_new_tokens=128, feature_flags={"memory": False}),
        context=ContextConfig(total_budget=900, relevant_memory_limit=2),
        tools=ToolConfig(approval_policy="never", shell_env_allowlist=("PATH",)),
        workers=WorkerConfig(max_depth=2),
    )

    agent = WhaleAgent(
        model_client=FakeModelClient(["<final>Done.</final>"]),
        workspace=workspace,
        session_store=store,
        config=config,
    )

    assert agent.approval_policy == "never"
    assert agent.max_steps == 4
    assert agent.max_new_tokens == 128
    assert agent.max_depth == 2
    assert agent.shell_env_allowlist == ("PATH",)
    assert agent.feature_flags == {"memory": False}
    assert agent.context_manager.total_budget == 900
    assert agent.context_manager.relevant_memory_limit == 2


def test_cli_provider_defaults_still_honor_environment_priority(tmp_path):
    class DummyModelClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.model = kwargs.get("model", "")
            self.base_url = kwargs.get("base_url", "")
            self.supports_prompt_cache = False

        def complete(self, prompt, max_new_tokens):
            raise AssertionError("model should not be invoked")

    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    with patch.dict(
        os.environ,
        {
            "WHALE_OPENAI_MODEL": "env-model",
            "WHALE_OPENAI_API_BASE": "https://example.test/v1",
            "WHALE_OPENAI_API_KEY": "sk-test",
        },
        clear=True,
    ), patch("whale.cli.OpenAICompatibleModelClient", DummyModelClient):
        args = whale_cli.build_arg_parser().parse_args(["--cwd", str(tmp_path), "--provider", "openai"])
        agent = whale_cli.build_agent(args)

    assert agent.model_client.model == "env-model"
    assert agent.model_client.base_url == "https://example.test/v1"
    assert agent.model_client.kwargs["api_key"] == "sk-test"
