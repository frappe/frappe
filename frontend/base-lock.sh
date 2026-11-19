#!/usr/bin/env bash
# Resolve `package.base.json` alone and write `yarn.lock.base`, reading nothing from the bench's apps.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# A sibling of `frontend/`, so the base file's `link:../ui` still points at the framework's `ui/`.
scratch="$(mktemp -d "$here/../.base-lock.XXXXXX")"
trap 'rm -rf "$scratch"' EXIT

cp "$here/package.base.json" "$scratch/package.json"
[ -f "$here/yarn.lock.base" ] && cp "$here/yarn.lock.base" "$scratch/yarn.lock"
yarn --cwd "$scratch" install --production=false --ignore-scripts >/dev/null
cp "$scratch/yarn.lock" "$here/yarn.lock.base"
echo "wrote $here/yarn.lock.base"
