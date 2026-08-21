#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"
SKILLS_DST="$HOME/.claude/skills"

mkdir -p "$SKILLS_DST"

echo "Linking skills into $SKILLS_DST ..."

for skill_dir in "$SKILLS_SRC"/*/; do
  skill_name="$(basename "$skill_dir")"
  target="$SKILLS_DST/$skill_name"
  if [ -L "$target" ] && [ -e "$target" ]; then
    echo "  (already linked) $skill_name"
  elif [ -L "$target" ]; then
    # Dangling symlink — e.g. the repo moved, or $HOME changed. Note that [ -L ] alone
    # is true for a broken link, so checking it first would silently skip the repair.
    rm "$target"
    ln -s "$skill_dir" "$target"
    echo "  Relinked (was broken): $skill_name"
  elif [ -e "$target" ]; then
    echo "  (SKIPPED — $skill_name already exists and is not a symlink)"
  else
    ln -s "$skill_dir" "$target"
    echo "  Linked: $skill_name"
  fi
done

# Install post-merge git hook so new skills are linked automatically after git pull
HOOK_SRC="$REPO_ROOT/.git-hooks/post-merge"
HOOK_DST="$REPO_ROOT/.git/hooks/post-merge"
if [ ! -f "$HOOK_DST" ]; then
  cp "$HOOK_SRC" "$HOOK_DST"
  chmod +x "$HOOK_DST"
  echo "Installed post-merge git hook"
else
  echo "  (already installed) post-merge git hook"
fi

echo "Done."
