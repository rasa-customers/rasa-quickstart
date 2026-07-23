"""Unit tests for scripts/maintenance/refresh_scaffold.py.

The scaffold-refresh automation regenerates `rasa init` output and diffs it
against template/. `rasa init` randomizes assistant_id, so the diff must
normalize that away; and our own added files (Makefile, README, ...) must not
count as differences.
"""

import pathlib
import sys

SETUP_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "maintenance"
sys.path.insert(0, str(SETUP_DIR))

import refresh_scaffold as rs  # noqa: E402


CONFIG = "recipe: default.v1\nassistant_id: piercing-heap\nlanguage: en\n"


def test_normalize_config_neutralizes_assistant_id():
    out = rs.normalize_for("config.yml", CONFIG)
    assert "piercing-heap" not in out
    assert "assistant_id:" in out


def test_normalize_config_stable_across_ids():
    a = rs.normalize_for("config.yml", "assistant_id: alpha-one\n")
    b = rs.normalize_for("config.yml", "assistant_id: beta-two\n")
    assert a == b


def test_normalize_non_config_unchanged():
    text = "provider: openai\n"
    assert rs.normalize_for("endpoints.yml", text) == text


def test_differing_files_detects_real_change(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    (gen / "actions").mkdir(parents=True); (tmpl / "actions").mkdir(parents=True)
    (gen / "actions" / "db.py").write_text("new\n")
    (tmpl / "actions" / "db.py").write_text("old\n")
    assert "actions/db.py" in rs.differing_files(str(gen), str(tmpl))


def test_differing_files_ignores_assistant_id_only(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    gen.mkdir(); tmpl.mkdir()
    (gen / "config.yml").write_text("assistant_id: aaa\nlanguage: en\n")
    (tmpl / "config.yml").write_text("assistant_id: zzz\nlanguage: en\n")
    assert rs.differing_files(str(gen), str(tmpl)) == []


def test_differing_files_flags_missing_in_template(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    gen.mkdir(); tmpl.mkdir()
    (gen / "new_flow.yml").write_text("x\n")
    assert "new_flow.yml" in rs.differing_files(str(gen), str(tmpl))


def test_differing_files_ignores_extra_template_files(tmp_path):
    gen = tmp_path / "gen"; tmpl = tmp_path / "tmpl"
    gen.mkdir(); tmpl.mkdir()
    (gen / "config.yml").write_text("language: en\n")
    (tmpl / "config.yml").write_text("language: en\n")
    (tmpl / "Makefile").write_text("setup:\n")  # our addition, not generated
    assert rs.differing_files(str(gen), str(tmpl)) == []
