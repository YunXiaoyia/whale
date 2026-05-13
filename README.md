# whale

`whale` 是一个运行在本地终端里的轻量级 coding agent。

如果用大白话说：它就是一个会在当前代码仓库里工作的命令行 AI 助手。你给它一句任务，它会先看仓库，再按受限制的工具去读文件、搜索代码、运行命令、修改文件，最后把结果告诉你。

它不是网页聊天窗口，而是一个“能操作本地项目”的终端程序。

## 这个项目适合做什么

- 让 AI 阅读当前仓库，并解释项目结构。
- 让 AI 帮你排查测试失败。
- 让 AI 做小范围代码修改。
- 让 AI 在多轮对话里记住刚刚读过的文件和当前任务。
- 让 AI 的每次操作都留下本地记录，方便复盘。

这个项目本身也很适合学习“一个简单 coding agent 是怎么做出来的”。

## 先理解几个概念

`coding agent`：不是只聊天的 AI，而是能围绕代码仓库执行任务的 AI。它通常会读文件、搜索、运行测试、改代码。

`CLI`：Command Line Interface，命令行界面。这里指你在终端里输入 `whale` 来启动程序。

`provider`：模型后端。比如 Ollama、OpenAI 兼容接口、Anthropic 兼容接口、DeepSeek。`whale` 本身不训练模型，它把请求发给这些后端。

`session`：一次可恢复的对话状态。`whale` 会把历史和记忆保存到 `.whale/sessions/`。

`run`：一次用户请求的运行记录。每次调用 `agent.ask()` 都会在 `.whale/runs/<run_id>/` 生成审计文件。

`tool`：AI 可以申请调用的工具。比如读文件、搜索、运行 shell、写文件。工具不是随便调用的，`whale` 会先校验和审批。

## 安装

需要 Python 3.10+。

如果你使用 `uv`：

```bash
uv sync
```

如果你使用普通 Python 环境：

```bash
pip install -e .
```

## 配置模型

第一次使用时，先复制环境变量模板：

```bash
cp .env.example .env
```

然后打开 `.env`，只填写你要用的模型后端。

当前项目支持这些 provider：

- `ollama`：本地 Ollama 模型。
- `openai`：OpenAI-compatible Responses API。
- `anthropic`：Anthropic-compatible Messages API。
- `deepseek`：DeepSeek 的 Anthropic-compatible API。

配置优先级是：

```text
命令行参数 > .env 里的 WHALE_* 变量 > 旧环境变量 > 代码默认值
```

不要把真实 API key 提交到仓库。`.env` 应该只留在本地。

## 快速开始

在当前仓库启动交互模式：

```bash
uv run whale --provider deepseek
```

指定另一个工作目录：

```bash
uv run whale --provider deepseek --cwd /path/to/repo
```

执行一次性任务，不进入交互模式：

```bash
uv run whale --provider deepseek "inspect the test failures and propose a fix"
```

如果你已经安装过包，也可以用模块入口：

```bash
python -m whale --provider deepseek
```

使用 Ollama：

```bash
ollama serve
ollama pull qwen3.5:4b
uv run whale --provider ollama --model qwen3.5:4b
```

## 交互命令

进入 `whale>` 后，可以使用这些命令：

- `/help`：查看内置命令。
- `/memory`：查看当前工作记忆。
- `/session`：查看当前 session 文件路径。
- `/reset`：清空当前 session 的历史和记忆。
- `/exit` 或 `/quit`：退出。

## 项目目录怎么读

建议新手按这个顺序读。

第一层，先看入口和整体流程：

- `pyproject.toml`：项目名、依赖、命令入口。
- `whale/cli.py`：用户在终端输入命令后，程序从这里开始装配。
- `whale/runtime.py`：agent 主循环，最核心的文件。

第二层，看 agent 有哪些能力：

- `whale/tools.py`：工具白名单，包括读文件、搜索、运行命令、写文件。
- `whale/models.py`：不同模型后端的统一适配层。
- `whale/workspace.py`：构建仓库快照，让模型先知道当前项目基本情况。

第三层，看上下文和记忆：

- `whale/context_manager.py`：把规则、工作区、记忆、历史和用户请求拼成 prompt。
- `whale/memory.py`：保存轻量工作记忆和持久记忆。
- `whale/run_store.py`：保存每次运行的 trace 和 report。
- `whale/task_state.py`：记录一次任务当前跑到哪里、为什么停止。

第四层，看测试：

- `tests/test_whale.py`：主流程测试。
- `tests/test_safety_invariants.py`：安全边界测试。
- `tests/test_context_manager.py`：上下文预算和历史压缩测试。
- `tests/test_memory.py`：记忆层测试。
- `tests/test_run_store.py`：运行记录落盘测试。

## 核心运行流程

可以把 `whale` 的一次任务理解成这条线：

```text
用户输入命令
  -> cli.py 解析参数
  -> build_agent() 装配模型、工作区、session
  -> Whale.ask() 开始一次任务
  -> ContextManager 组装 prompt
  -> models.py 调用模型后端
  -> runtime.py 解析模型输出
  -> 如果模型要调用工具，就交给 tools.py 执行
  -> 工具结果写入 history / memory / trace
  -> 继续下一轮，直到模型给出 final answer
```

用更直观的话说：

1. `cli.py` 负责“怎么启动”。
2. `runtime.py` 负责“怎么循环工作”。
3. `context_manager.py` 负责“给模型看什么上下文”。
4. `models.py` 负责“怎么请求模型”。
5. `tools.py` 负责“模型能做什么动作”。
6. `memory.py` 和 `.whale/` 负责“怎么记住和复盘”。

## 最重要的文件解释

### `whale/cli.py`

这是命令行入口。

它负责解析这些参数：

- `--provider`
- `--model`
- `--cwd`
- `--resume`
- `--approval`
- `--max-steps`
- `--max-new-tokens`

然后它会调用 `build_agent()`，把模型客户端、工作区快照、session store、审批策略等对象装配成一个 `Whale` 实例。

如果用户传了 prompt，程序会跑 one-shot 模式。没有传 prompt，就进入 `whale>` 交互循环。

### `whale/runtime.py`

这是项目最核心的文件。

里面的 `Whale.ask()` 是主流程。它会反复做四件事：

1. 组装 prompt。
2. 调模型。
3. 解析模型输出。
4. 执行工具或返回最终答案。

`run_tool()` 是工具执行总闸口。所有工具调用都要经过这里校验，包括工具是否存在、参数是否合法、是否重复调用、是否需要审批、是否越过工作区边界。

如果你想理解 agent 是怎么跑起来的，优先读 `Whale.ask()` 和 `Whale.run_tool()`。

### `whale/tools.py`

这个文件定义了模型能申请的工具。

目前主要工具有：

- `list_files`：列出工作区文件。
- `read_file`：按行读取 UTF-8 文件。
- `search`：用 `rg` 搜索代码，找不到 `rg` 时使用简单 fallback。
- `run_shell`：在仓库根目录运行 shell 命令。
- `write_file`：写入文本文件。
- `patch_file`：用精确文本替换修改文件。
- `delegate`：派一个受限的只读子 agent 做调查。

其中 `run_shell`、`write_file`、`patch_file` 是高风险工具，需要受审批策略控制。

### `whale/models.py`

这个文件把不同模型服务统一成一个接口：

```python
client.complete(prompt, max_new_tokens)
```

这样 `runtime.py` 不需要关心底层是 Ollama、OpenAI-compatible、Anthropic-compatible 还是 DeepSeek。

### `whale/context_manager.py`

这个文件负责控制 prompt 大小。

每一轮发给模型的内容包括：

- 稳定规则和工具说明。
- 当前工作区快照。
- 工作记忆。
- 相关记忆。
- 最近历史。
- 当前用户请求。

如果内容太长，它会按固定顺序压缩上下文，优先保留当前请求和关键上下文。

### `whale/memory.py`

这个文件负责让 agent “记得一点东西”，但不是把所有内容都塞进 prompt。

它主要保存：

- 当前任务摘要。
- 最近读写过的文件。
- 文件短摘要。
- 临时笔记。
- 持久记忆主题。

这样下一轮对话还能接上，但不会因为历史太长而失控。

### `whale/workspace.py`

这个文件负责生成仓库第一印象。

它会收集：

- 当前目录。
- Git 根目录。
- 当前分支。
- 默认分支。
- `git status`。
- 最近提交。
- 少量项目文档，例如 `README.md`、`pyproject.toml`。

这些信息会进入 prompt，让模型不用一开始就完全盲猜。

## 安全设计

`whale` 不是让模型直接操作电脑，而是把操作限制在工具层。

主要安全点：

- 文件路径会被限制在 workspace root 内，防止 `../` 或符号链接逃逸。
- 高风险工具需要审批策略控制。
- shell 命令只拿到 allowlist 环境变量，减少 secret 泄漏风险。
- trace 和 report 会对配置过的 secret 做脱敏。
- 重复的相同工具调用会被拒绝，避免模型卡在坏循环里。
- 子 agent 默认只读，不能替父 agent 写文件。

审批策略有三种：

- `--approval ask`：高风险动作执行前询问。
- `--approval auto`：自动允许高风险动作。
- `--approval never`：拒绝高风险动作。

新手建议先用默认的 `ask`。

## 本地状态文件

运行后，项目根目录下会出现 `.whale/`。

常见内容：

```text
.whale/
  sessions/
    <session_id>.json
  runs/
    <run_id>/
      task_state.json
      trace.jsonl
      report.json
  memory/
    MEMORY.md
    topics/
```

这些文件用于本地恢复、记忆和复盘，通常不需要提交到 Git。

## 常见开发任务

运行测试：

```bash
uv run pytest -q
```

运行 Ruff 检查：

```bash
uv run ruff check .
```

查看命令行参数：

```bash
uv run whale --help
```

用 fake model 写测试：

```python
from whale import FakeModelClient, Whale
```

项目测试里大量使用 `FakeModelClient`，这样不需要真实请求模型，也能测试 agent 主循环。

## 新手入门路线

如果你只是想会用：

1. 读 `快速开始`。
2. 配置 `.env`。
3. 运行 `uv run whale --provider deepseek`。
4. 在 `whale>` 里问它：“请阅读这个仓库并解释结构”。

如果你想读懂代码：

1. 先看 `whale/cli.py` 的 `main()` 和 `build_agent()`。
2. 再看 `whale/runtime.py` 的 `Whale.ask()`。
3. 再看 `whale/tools.py` 的工具定义。
4. 最后看 `context_manager.py` 和 `memory.py`。

如果你想改功能：

1. 想新增 CLI 参数，改 `whale/cli.py`。
2. 想新增模型后端，改 `whale/models.py` 和 `whale/cli.py`。
3. 想新增 agent 工具，改 `whale/tools.py`，并给 `tests/` 加测试。
4. 想改 prompt 结构，改 `whale/runtime.py` 的 `build_prefix()` 或 `whale/context_manager.py`。
5. 想改记忆行为，改 `whale/memory.py` 和 `runtime.py` 里的 `update_memory_after_tool()`。

## 常见问题

### 为什么模型必须输出 `<tool>` 或 `<final>`？

因为 `runtime.py` 需要把模型输出解析成明确动作。

`<tool>` 表示模型要调用工具，例如读文件。

`<final>` 表示模型已经完成任务，可以把答案返回给用户。

这种格式让控制流更稳定，也更容易测试。

### 为什么有些工具会被拒绝？

通常有几类原因：

- 参数不合法。
- 路径逃出了工作区。
- 高风险工具没有通过审批。
- 最近已经重复调用过同一个工具。
- 子 agent 是只读模式。

### 为什么不直接把整个仓库塞给模型？

仓库可能很大，模型上下文有限，而且越多内容越容易混乱。

`whale` 的做法是先给模型一份小的 workspace 快照，再让模型按需读文件。这样更省上下文，也更贴近真实 coding agent 的工作方式。

### 这个项目有没有外部依赖？

运行包本身没有声明运行时依赖。开发测试依赖在 `pyproject.toml` 的 `dev` 组里，主要是 `pytest` 和 `ruff`。

### 我该从哪里开始调试？

优先看一次运行生成的：

- `.whale/runs/<run_id>/task_state.json`
- `.whale/runs/<run_id>/trace.jsonl`
- `.whale/runs/<run_id>/report.json`

如果是代码逻辑问题，再去看 `whale/runtime.py` 和对应测试。

## 一句话总结

`whale` 是一个小而完整的本地 coding agent 示例：CLI 负责启动，runtime 负责主循环，models 负责模型适配，tools 负责受控行动，context 和 memory 负责让模型带着合适上下文继续工作。
