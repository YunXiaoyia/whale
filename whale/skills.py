"""Safe local skill discovery for Whale V1.

Skills are markdown instruction files. This module only discovers and parses
`SKILL.md`; it does not execute anything referenced by a skill.
"""

from dataclasses import dataclass
import re
from pathlib import Path

from .config import DEFAULT_SKILL_CONFIG
from .workspace import clip


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    triggers: tuple[str, ...]
    source_path: Path
    scope: str
    instructions: str
    enabled: bool = True


def default_skill_roots(repo_root, home_root=None):
    repo_root = Path(repo_root)
    home_root = Path.home() if home_root is None else Path(home_root)
    return (
        ("project", repo_root / "skills"),
        ("project", repo_root / ".whale" / "skills"),
        ("user", home_root / ".whale" / "skills"),
    )


def discover_skills(repo_root, home_root=None, config=None):
    config = config or DEFAULT_SKILL_CONFIG
    if not config.enabled:
        return []
    manifests = []
    for scope, root in default_skill_roots(repo_root, home_root=home_root):
        manifests.extend(discover_skills_in_root(root, scope=scope, config=config))
        if len(manifests) >= config.max_discovered:
            return manifests[: config.max_discovered]
    return manifests


def discover_skills_in_root(root, scope, config=None):
    config = config or DEFAULT_SKILL_CONFIG
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        return []
    manifests = []
    for path in sorted(root.rglob(config.filename)):
        manifest = parse_skill_file(path, root=root, scope=scope, config=config)
        if manifest is not None:
            manifests.append(manifest)
        if len(manifests) >= config.max_discovered:
            break
    return manifests


def parse_skill_file(path, root, scope, config=None):
    config = config or DEFAULT_SKILL_CONFIG
    path = Path(path).resolve()
    root = Path(root).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    if path.name != config.filename:
        return None
    name = _skill_name_from_relative(relative)
    if not re.match(config.name_pattern, name):
        return None
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeError:
        return None
    metadata, instructions = _split_front_matter(body)
    enabled = _parse_bool(metadata.get("enabled", "true"))
    description = metadata.get("description", "") or _infer_description(instructions)
    triggers = _parse_triggers(metadata.get("triggers", ""))
    return SkillManifest(
        name=name,
        description=clip(description.strip(), 240),
        triggers=tuple(triggers),
        source_path=path,
        scope=scope,
        instructions=clip(instructions.strip(), int(config.instruction_char_limit)),
        enabled=enabled,
    )


def _skill_name_from_relative(relative):
    parent = relative.parent
    if str(parent) in ("", "."):
        return relative.stem.lower()
    return "-".join(parent.parts)


def _split_front_matter(text):
    text = str(text)
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw_meta = text[4:end]
    body = text[end + len("\n---"):].lstrip("\n")
    return _parse_simple_front_matter(raw_meta), body


def _parse_simple_front_matter(text):
    metadata = {}
    current_key = ""
    current_items = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("- ") and current_key:
            current_items.append(line[2:].strip())
            metadata[current_key] = ", ".join(current_items)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip().lower()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        metadata[current_key] = value.strip("\"'")
        current_items = []
    return metadata


def _infer_description(text):
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            return line.lstrip("#").strip()
        return line
    return ""


def _parse_triggers(value):
    value = str(value or "").strip()
    if not value:
        return ()
    return tuple(
        item.strip().strip("\"'")
        for item in value.split(",")
        if item.strip().strip("\"'")
    )


def _parse_bool(value):
    return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}
