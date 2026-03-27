#!/usr/bin/env bash
set -euo pipefail

# Bundle web build artifacts into the Python package.
# Usage: ./scripts/bundle_web.sh
#
# Prerequisites: Node.js >= 18, npm

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_DIR="$REPO_ROOT/web"
STATIC_DIR="$REPO_ROOT/src/maestro/_static"

echo "==> Installing web dependencies..."
cd "$WEB_DIR"
npm ci --silent

echo "==> Building web dashboard..."
npm run build

echo "==> Bundling into Python package..."
# Clean previous bundle (keep .gitkeep)
find "$STATIC_DIR" -mindepth 1 ! -name '.gitkeep' -delete

# Copy build output
cp -r "$WEB_DIR/dist/"* "$STATIC_DIR/"

echo "==> Done. Bundled files:"
ls -la "$STATIC_DIR/"
