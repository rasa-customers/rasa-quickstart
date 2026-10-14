"""Unit tests for scripts/maintenance/refresh_scaffold.py.

The scaffold-refresh automation copies the Mantle template bundled with
rasa-pro and diffs it against template/. `rasa train` writes a generated
agent.id into agent.yml, so the diff must normalize that away; and our own
added files (Makefile, README, ...) must not count as differences.
"""

import pathlib
import sys

SETUP_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "maintenance"
sys.path.insert(0, str(SETUP_DIR))

import refresh_scaffold as rs  # noqa: E402


AGENT = "agent:\n  language: en\n  persona: |\n    Be nice.\nrules:\n- Be polite.\n"
AGENT_TRAINED = AGENT.replace(
    "agent:\n", "agent:\n  id: 20261014-093329-elaborate-atmosphere\n"
)


def test_normalize_agent_drops_generated_id():
    assert rs.normalize_for("agent.yml", AGENT_TRAINED) == AGENT


def test_normalize_agent_keeps_persona_lines():
    # Only the two-space `id:` key goes; deeper-indented text is untouched.
    text = "agent:\n  persona: |\n    id: is a word here\n"
    assert rs.normalize_for("agent.yml", text) == text


def test_normalize_other_files_unchanged():
    text = "  id: orchestrator\n"
    assert rs.normalize_for("integrations.yml", text) == text


def test_differing_files_detects_real_change(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    skill = pathlib.Path("skills") / "view_transactions"
    (gen / skill).mkdir(parents=True); (tmpl / skill).mkdir(parents=True)
    (gen / skill / "tools.py").write_text("new\n")
    (tmpl / skill / "tools.py").write_text("old\n")
    assert "skills/view_transactions/tools.py" in rs.differing_files(str(gen), str(tmpl))


def test_differing_files_ignores_agent_id_only(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    gen.mkdir(); tmpl.mkdir()
    (gen / "agent.yml").write_text(AGENT)
    (tmpl / "agent.yml").write_text(AGENT_TRAINED)
    assert rs.differing_files(str(gen), str(tmpl)) == []


def test_differing_files_flags_missing_in_template(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    (gen / "skills" / "new_skill").mkdir(parents=True); tmpl.mkdir()
    (gen / "skills" / "new_skill" / "skill.md").write_text("x\n")
    assert "skills/new_skill/skill.md" in rs.differing_files(str(gen), str(tmpl))


def test_differing_files_ignores_extra_template_files(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    gen.mkdir(); tmpl.mkdir()
    (gen / "agent.yml").write_text(AGENT)
    (tmpl / "agent.yml").write_text(AGENT)
    (tmpl / "Makefile").write_text("setup:\n")  # our addition, not generated
    assert rs.differing_files(str(gen), str(tmpl)) == []


def test_differing_files_skips_per_developer_output(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    (gen / ".claude" / "skills").mkdir(parents=True)
    (gen / "skills" / "s" / "__pycache__").mkdir(parents=True)
    tmpl.mkdir()
    (gen / ".env").write_text("RASA_LICENSE=x\n")
    (gen / ".claude" / "skills" / "SKILL.md").write_text("x\n")
    (gen / "skills" / "s" / "__pycache__" / "tools.cpython-311.pyc").write_text("x")
    assert rs.differing_files(str(gen), str(tmpl)) == []


def test_template_matches_its_own_generated_copy(tmp_path):
    # Copying template/ into a "generated" dir must report no differences,
    # i.e. the normalization and skip rules agree with the committed tree.
    template = pathlib.Path(__file__).resolve().parents[1] / "template"
    gen = tmp_path / "gen"
    for rel in ["AGENTS.md", "agent.yml", "integrations.yml"]:
        (gen / rel).parent.mkdir(parents=True, exist_ok=True)
        (gen / rel).write_text((template / rel).read_text())
    assert rs.differing_files(str(gen), str(template)) == []
