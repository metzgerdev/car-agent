#!/usr/bin/env bash
# Build and deploy this repository to an existing Hugging Face Docker Space.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/deploy_huggingface.sh [owner/space-name]

Pushes the current Git branch to the metzgerdev/car-sales-agent Hugging Face
Space by default. Pass an owner/space-name to override it. Authenticate Git
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
space_url="https://huggingface.co/spaces/${space_repo}.git"

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
    echo "Error: remote '$remote_name' points to $configured_url, not $space_url." >&2
    exit 1
  fi
else
  git remote add "$remote_name" "$space_url"
fi

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
  echo "Error: deployment requires a checked-out branch." >&2
  exit 1
fi

git push "$remote_name" "HEAD:refs/heads/main"

printf '\nDeployment submitted: https://huggingface.co/spaces/%s\n' "$space_repo"
printf 'Confirm OPENROUTER_API_KEY is set as a Space secret before using live chat.\n'
