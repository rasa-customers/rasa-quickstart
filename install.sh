#!/usr/bin/env bash
#
# Rasa Quickstart bootstrap (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.sh | bash
#
# Optionally pass a target directory and setup flags:
#
#   ... | bash -s -- --ides claude,cursor --provider openai my-agent
#
# It installs uv (if missing), downloads the delivered project (template/),
# starts a fresh git repo, and runs the setup (venv + skills + a trained model).
#
# Set DRY_RUN=1 to print the plan without doing anything.

set -eu

REPO="${RASA_QUICKSTART_REPO:-rasa-customers/rasa-quickstart}"
REF="${RASA_QUICKSTART_REF:-main}"
DRY_RUN="${DRY_RUN:-}"

usage() {
  cat <<'EOF'
Usage: install.sh [--ides LIST] [--provider NAME] [--yes] [TARGET_DIR]

  --ides LIST       coding agents to wire up (e.g. claude,cursor,vscode)
  --provider NAME   LLM provider: openai (default) or anthropic
  --yes             accept detected defaults, no prompts
  --skip-train      skip the final `rasa train`
  TARGET_DIR        directory to create (default: rasa-quickstart)
EOF
}

IDES=""
PROVIDER=""
ASSUME_YES=""
SKIP_TRAIN=""
TARGET=""

while [ $# -gt 0 ]; do
  case "$1" in
    --ides) IDES="$2"; shift 2 ;;
    --ides=*) IDES="${1#*=}"; shift ;;
    --provider) PROVIDER="$2"; shift 2 ;;
    --provider=*) PROVIDER="${1#*=}"; shift ;;
    --yes|-y) ASSUME_YES="1"; shift ;;
    --skip-train) SKIP_TRAIN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    *) TARGET="$1"; shift ;;
  esac
done

[ -n "$TARGET" ] || TARGET="rasa-quickstart"

# Values contain no spaces, so a plain string forwards them safely.
SETUP_ARGS=""
[ -n "$IDES" ] && SETUP_ARGS="$SETUP_ARGS --ides $IDES"
[ -n "$PROVIDER" ] && SETUP_ARGS="$SETUP_ARGS --provider $PROVIDER"
[ -n "$ASSUME_YES" ] && SETUP_ARGS="$SETUP_ARGS --yes"
[ -n "$SKIP_TRAIN" ] && SETUP_ARGS="$SETUP_ARGS --skip-train"

# RASA_QUICKSTART_TARBALL lets CI (or an offline mirror) override the source.
TARBALL="${RASA_QUICKSTART_TARBALL:-https://github.com/$REPO/archive/refs/heads/$REF.tar.gz}"

plan() { echo "PLAN: $*"; }

ensure_uv() {
  if [ -n "$DRY_RUN" ]; then plan "ensure uv is installed"; return; fi
  if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # uv installs to ~/.local/bin by default
    export PATH="$HOME/.local/bin:$PATH"
  fi
}

fetch_template() {
  if [ -n "$DRY_RUN" ]; then
    plan "fetch $TARBALL"
    plan "extract template/ into $TARGET"
    return
  fi
  if [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
    echo "Error: '$TARGET' already exists and is not empty." >&2
    exit 1
  fi
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  case "$TARBALL" in
    http://*|https://*)
      echo "Downloading project..."
      curl -fsSL "$TARBALL" | tar -xz -C "$tmp" ;;
    *)
      echo "Extracting project from $TARBALL..."
      tar -xz -C "$tmp" -f "$TARBALL" ;;
  esac
  mkdir -p "$TARGET"
  # Tarball extracts to a single <repo>-<ref>/ directory; copy its template/.
  cp -R "$tmp"/*/template/. "$TARGET"/
}

git_init() {
  if [ -n "$DRY_RUN" ]; then plan "git init in $TARGET"; return; fi
  ( cd "$TARGET" && git init -q )
}

run_setup() {
  if [ -n "$DRY_RUN" ]; then
    plan "(cd $TARGET) uv run python scripts/setup.py$SETUP_ARGS"
    return
  fi
  # shellcheck disable=SC2086
  ( cd "$TARGET" && uv run python scripts/setup.py $SETUP_ARGS )
}

ensure_uv
fetch_template
git_init
run_setup

if [ -z "$DRY_RUN" ]; then
  echo ""
  echo "Done. Next:"
  echo "  cd $TARGET"
  echo "  # add RASA_LICENSE and your LLM key to .env, then:"
  echo "  make inspect"
fi
