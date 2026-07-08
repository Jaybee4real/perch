#!/usr/bin/env bash
# Installs perch: symlinks the script into ~/.local/bin and seeds the project
# registry into ~/.config/perch (without overwriting one you already have).
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="$HOME/.local/bin"
config_dir="$HOME/.config/perch"

mkdir -p "$bin_dir" "$config_dir"
chmod +x "$repo_dir/perch"

ln -sf "$repo_dir/perch" "$bin_dir/perch"
# pz-dev was perch's old name; keep it working for old muscle memory and scripts.
ln -sfn perch "$bin_dir/pz-dev"

if [ ! -f "$config_dir/projects.conf" ]; then
  cp "$repo_dir/projects.conf" "$config_dir/projects.conf"
  echo "Seeded $config_dir/projects.conf"
else
  echo "Kept existing $config_dir/projects.conf (repo copy not applied)"
fi

echo "Installed: $bin_dir/perch -> $repo_dir/perch"
case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *) echo "NOTE: $bin_dir is not on your PATH — add it to your shell profile." ;;
esac

echo "Try: perch doctor   (then: perch list)"
