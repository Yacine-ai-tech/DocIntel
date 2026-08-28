#!/usr/bin/env bash
# Installs repo-local git hooks that enforce the sole-authorship rule
# from .agents/skills/github-collaboration/SKILL.md. Run once after cloning.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
cp scripts/git-hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
echo "Installed commit-msg hook (blocks AI/bot co-authorship trailers)."
