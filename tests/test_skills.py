from pathlib import Path

from whale.config import SkillConfig
from whale.skills import discover_skills, parse_skill_file


def write_skill(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_discover_skills_loads_project_whale_and_user_roots(tmp_path):
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    write_skill(
        repo / "skills" / "python-testing" / "SKILL.md",
        "---\n"
        "description: Run focused Python tests.\n"
        "triggers: pytest, unit tests\n"
        "---\n"
        "# Python testing\n"
        "Use pytest for focused checks.\n",
    )
    write_skill(
        repo / ".whale" / "skills" / "repo-default" / "SKILL.md",
        "# Repo default\nPrefer existing local patterns.\n",
    )
    write_skill(
        home / ".whale" / "skills" / "personal" / "SKILL.md",
        "---\nenabled: false\ntriggers:\n- personal\n---\n# Personal\nUser scoped notes.\n",
    )

    manifests = discover_skills(repo, home_root=home)

    assert [manifest.name for manifest in manifests] == ["python-testing", "repo-default", "personal"]
    assert [manifest.scope for manifest in manifests] == ["project", "project", "user"]
    assert manifests[0].description == "Run focused Python tests."
    assert manifests[0].triggers == ("pytest", "unit tests")
    assert manifests[0].instructions.startswith("# Python testing")
    assert manifests[2].enabled is False


def test_discover_skills_allows_nested_skill_directories(tmp_path):
    write_skill(tmp_path / "skills" / "lang" / "python-testing" / "SKILL.md", "# Python testing\n")

    manifests = discover_skills(tmp_path)

    assert [manifest.name for manifest in manifests] == ["lang-python-testing"]
    assert manifests[0].source_path == (tmp_path / "skills" / "lang" / "python-testing" / "SKILL.md").resolve()


def test_parse_skill_file_rejects_paths_outside_discovery_root(tmp_path):
    root = tmp_path / "skills"
    outside = tmp_path / "outside" / "safe-name" / "SKILL.md"
    write_skill(outside, "# Outside\n")

    manifest = parse_skill_file(outside, root=root, scope="project")

    assert manifest is None


def test_discover_skills_skips_invalid_names_and_non_skill_files(tmp_path):
    write_skill(tmp_path / "skills" / "bad.name" / "SKILL.md", "# Bad\n")
    write_skill(tmp_path / "skills" / "valid-name" / "README.md", "# Not a skill\n")
    write_skill(tmp_path / "skills" / "valid-name" / "SKILL.md", "# Valid\n")

    manifests = discover_skills(tmp_path)

    assert [manifest.name for manifest in manifests] == ["valid-name"]


def test_skill_instructions_are_clipped_by_config(tmp_path):
    path = write_skill(tmp_path / "skills" / "tiny" / "SKILL.md", "# Tiny\n" + ("A" * 100))

    manifest = parse_skill_file(
        path,
        root=Path(tmp_path / "skills"),
        scope="project",
        config=SkillConfig(instruction_char_limit=20),
    )

    assert manifest is not None
    assert manifest.instructions.startswith("# Tiny")
    assert "[truncated" in manifest.instructions
    assert "A" * 30 not in manifest.instructions
