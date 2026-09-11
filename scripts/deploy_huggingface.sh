#!/usr/bin/env bash
# Build and deploy this repository to an existing Hugging Face Docker Space.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/deploy_huggingface.sh [owner/space-name]

Creates a single-commit Space snapshot from the current Git branch and pushes
it to metzgerdev/car-sales-agent by default. The snapshot omits the
documentation screenshot that Hugging Face rejects as a raw binary file. Pass
an owner/space-name to override it. Authenticate Git with an SSH key registered
with Hugging Face before running this command. To skip the local Docker
preflight build, set SKIP_DOCKER_BUILD=1.

Example:
  scripts/deploy_huggingface.sh
  scripts/deploy_huggingface.sh my-username/my-space
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

space_repo="${1:-metzgerdev/car-sales-agent}"
if [[ ! "$space_repo" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  usage >&2
  exit 2
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
space_url="git@hf.co:spaces/${space_repo}.git"
legacy_https_url="https://huggingface.co/spaces/${space_repo}.git"

cd "$project_root"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: deployment must run from a Git working tree." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Error: commit or stash all changes before deploying." >&2
  git status --short >&2
  exit 1
fi

if [[ "${SKIP_DOCKER_BUILD:-0}" != "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is required for the preflight build. Set SKIP_DOCKER_BUILD=1 to skip it." >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Error: Docker Desktop is not reachable.

Start or restart Docker Desktop, wait until it reports that the engine is
running, then retry. To deploy without the optional local Docker preflight
build, run:

  SKIP_DOCKER_BUILD=1 ./scripts/deploy_huggingface.sh
EOF
    exit 1
  fi
  if ! docker buildx inspect --bootstrap >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Error: Docker's active buildx builder is unavailable.

Restart Docker Desktop, then retry. To deploy without the optional local
Docker preflight build, run:

  SKIP_DOCKER_BUILD=1 ./scripts/deploy_huggingface.sh
EOF
    exit 1
  fi
  docker build --load --tag classic-car-advisor:space .
fi

remote_name="huggingface"
if git remote get-url "$remote_name" >/dev/null 2>&1; then
  configured_url="$(git remote get-url "$remote_name")"
  if [[ "$configured_url" != "$space_url" ]]; then
    if [[ "$configured_url" == "$legacy_https_url" ]]; then
      git remote set-url "$remote_name" "$space_url"
      printf "Updated '%s' remote to use SSH.\n" "$remote_name"
    else
      echo "Error: remote '$remote_name' points to $configured_url, not $space_url." >&2
      exit 1
    fi
  fi
else
  git remote add "$remote_name" "$space_url"
fi

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
  echo "Error: deployment requires a checked-out branch." >&2
  exit 1
fi

source_commit="$(git rev-parse --short HEAD)"
author_name="$(git log -1 --format=%an HEAD)"
author_email="$(git log -1 --format=%ae HEAD)"
snapshot_dir="$(mktemp -d "${TMPDIR:-/tmp}/car-agent-space.XXXXXX")"

cleanup() {
  rm -rf "$snapshot_dir"
}
trap cleanup EXIT

git archive --format=tar HEAD | tar -x -C "$snapshot_dir"
rm -f "$snapshot_dir/docs/ui-demo.png"
sed '/^!\[Grand Prix Motors chat UI\](docs\/ui-demo\.png)$/d' "$snapshot_dir/README.md" \
  > "$snapshot_dir/README.md.snapshot"
mv "$snapshot_dir/README.md.snapshot" "$snapshot_dir/README.md"

git -C "$snapshot_dir" init --initial-branch=main --quiet
git -C "$snapshot_dir" config user.name "$author_name"
git -C "$snapshot_dir" config user.email "$author_email"
git -C "$snapshot_dir" add --all
git -C "$snapshot_dir" commit --quiet -m "Deploy ${source_commit}"
git -C "$snapshot_dir" remote add "$remote_name" "$space_url"

# A Space snapshot is intentionally unrelated to the source repository's
# history, so every deployment replaces the previous snapshot. Fetch first and
# use an explicit lease to avoid overwriting a simultaneous remote update.
git fetch "$remote_name" main
remote_tip="$(git rev-parse "refs/remotes/${remote_name}/main")"
git -C "$snapshot_dir" push \
  --force-with-lease="refs/heads/main:${remote_tip}" \
  "$remote_name" "HEAD:refs/heads/main"
git fetch "$remote_name" main

printf '\nDeployment submitted: https://huggingface.co/spaces/%s\n' "$space_repo"
printf 'Published Space snapshot for source commit %s.\n' "$source_commit"
printf 'Confirm OPENROUTER_API_KEY is set as a Space secret before using live chat.\n'
