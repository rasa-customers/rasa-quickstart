#!/usr/bin/env python3
"""Keep template/'s committed scaffold in sync with `rasa init --engine mantle`.

`rasa init --engine mantle` copies the Mantle project template bundled inside
rasa-pro (`rasa.cli.scaffold.scaffold_path("mantle")`) and then runs
interactive, license-gated setup (secrets, skills, docs, training). Only the
copied files matter here, so we copy the bundled template directly: no
license, LLM key, or network needed.

`rasa train` writes a generated `agent.id` into agent.yml, so that line is
normalized away before comparing (a maintainer who trained inside template/
should not see a spurious diff). Files we add on top of the scaffold
(Makefile, README, scripts/, ...) are ignored because we only compare files
the scaffold actually produces.

Usage:
    refresh_scaffold.py [--template-dir template] [--generated-dir DIR]
                        [--python python] [--apply]

Exit code 0 = in sync (or --apply succeeded); 1 = differences found.
"""

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

# Directories that must never be compared/committed.
_SKIP_DIRS = {".rasa", ".claude", ".cursor", "models", "__pycache__"}
# Files `rasa init` writes that are per-developer, never part of the scaffold.
_SKIP_FILES = {".env"}

# `agent.id` as written by `rasa train`, e.g. "  id: 20261014-093329-bold-spring".
_AGENT_ID_RE = re.compile(r"(?m)^  id:.*\n")

_SCAFFOLD_PATH_SNIPPET = (
    "from rasa.cli.scaffold import scaffold_path; print(scaffold_path('mantle'))"
)


def normalize_agent(text):
    return _AGENT_ID_RE.sub("", text)


def normalize_for(relpath, text):
    if relpath == "agent.yml":
        return normalize_agent(text)
    return text


def _iter_files(root):
    root = pathlib.Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name in _SKIP_FILES or name.endswith(".pyc"):
                continue
            full = pathlib.Path(dirpath) / name
            yield full.relative_to(root).as_posix()


def differing_files(generated_dir, template_dir):
    generated_dir = pathlib.Path(generated_dir)
    template_dir = pathlib.Path(template_dir)
    diffs = []
    for rel in _iter_files(generated_dir):
        gen_text = (generated_dir / rel).read_text()
        tmpl_path = template_dir / rel
        if not tmpl_path.exists():
            diffs.append(rel)
            continue
        if normalize_for(rel, gen_text) != normalize_for(rel, tmpl_path.read_text()):
            diffs.append(rel)
    return sorted(diffs)


def bundled_scaffold_path(python):
    out = subprocess.run(
        [*python, "-c", _SCAFFOLD_PATH_SNIPPET],
        check=True, capture_output=True, text=True,
    )
    # The last line: rasa may log to stdout before the path is printed.
    return pathlib.Path(out.stdout.strip().splitlines()[-1])


def generate_scaffold(dest, python):
    dest = pathlib.Path(dest)
    shutil.copytree(bundled_scaffold_path(python), dest, dirs_exist_ok=True)
    for junk in _SKIP_DIRS:
        for path in list(dest.rglob(junk)):
            shutil.rmtree(path, ignore_errors=True)
    return dest


def apply_changes(generated_dir, template_dir, paths):
    generated_dir = pathlib.Path(generated_dir)
    template_dir = pathlib.Path(template_dir)
    for rel in paths:
        src = generated_dir / rel
        dst = template_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text())


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Refresh the committed scaffold.")
    parser.add_argument("--template-dir", default="template")
    parser.add_argument("--generated-dir", default=None,
                        help="Use an already-generated scaffold instead of the "
                             "one bundled with the installed rasa-pro")
    parser.add_argument("--python", default="python",
                        help="Python with rasa-pro installed (space-separated, "
                             "e.g. 'uv run python')")
    parser.add_argument("--apply", action="store_true",
                        help="Copy differences into the template dir")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tmp = None
    try:
        if args.generated_dir:
            generated = args.generated_dir
        else:
            tmp = tempfile.mkdtemp(prefix="rasa-scaffold-")
            generated = generate_scaffold(tmp, args.python.split())
        diffs = differing_files(generated, args.template_dir)
        if not diffs:
            print("Scaffold is up to date.")
            return 0
        print("Scaffold differs from `rasa init --engine mantle` output:")
        for rel in diffs:
            print("  " + rel)
        if args.apply:
            apply_changes(generated, args.template_dir, diffs)
            print("Applied %d change(s) to %s." % (len(diffs), args.template_dir))
            return 0
        return 1
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
