#!/usr/bin/env python3
"""Keep template/'s committed scaffold in sync with `rasa init`.

Regenerates the default CALM scaffold with the installed Rasa version and
diffs it against template/. `rasa init` randomizes `assistant_id`, so that
field is normalized before comparing. Files we add on top of the scaffold
(Makefile, README, scripts/, ...) are ignored because we only compare files
that `rasa init` actually produces.

Usage:
    refresh_scaffold.py [--template-dir template] [--generated-dir DIR]
                        [--rasa-bin rasa] [--apply]

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

# Directories `rasa init` may leave behind that must never be compared/committed.
_SKIP_DIRS = {".rasa", "models", "__pycache__"}

_ASSISTANT_ID_RE = re.compile(r"(?m)^(assistant_id:).*$")


def normalize_config(text):
    return _ASSISTANT_ID_RE.sub(r"\1 <id>", text)


def normalize_for(relpath, text):
    if relpath == "config.yml":
        return normalize_config(text)
    return text


def _iter_files(root):
    root = pathlib.Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
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


def generate_scaffold(dest, rasa_bin):
    dest = pathlib.Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [*rasa_bin, "init", "--template", "default", "--init-dir", str(dest),
         "--no-prompt"],
        check=True,
    )
    for junk in _SKIP_DIRS:
        shutil.rmtree(dest / junk, ignore_errors=True)
    return dest


def apply_changes(generated_dir, template_dir, paths):
    generated_dir = pathlib.Path(generated_dir)
    template_dir = pathlib.Path(template_dir)
    for rel in paths:
        src = generated_dir / rel
        dst = template_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text()
        if rel == "config.yml" and dst.exists():
            # Keep the committed assistant_id to avoid churn.
            old = _ASSISTANT_ID_RE.search(dst.read_text())
            if old:
                text = _ASSISTANT_ID_RE.sub(old.group(0), text)
        dst.write_text(text)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Refresh the committed scaffold.")
    parser.add_argument("--template-dir", default="template")
    parser.add_argument("--generated-dir", default=None,
                        help="Use an already-generated scaffold instead of running rasa init")
    parser.add_argument("--rasa-bin", default="rasa",
                        help="Rasa executable (space-separated, e.g. 'uv run rasa')")
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
            generated = generate_scaffold(tmp, args.rasa_bin.split())
        diffs = differing_files(generated, args.template_dir)
        if not diffs:
            print("Scaffold is up to date.")
            return 0
        print("Scaffold differs from `rasa init` output:")
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
