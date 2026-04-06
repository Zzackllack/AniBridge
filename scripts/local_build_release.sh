#!/usr/bin/env bash
set -euo pipefail

# Local artifact build helper
# - builds sdist/wheel
# - generates SHA256SUMS
# - builds a PyInstaller single-file binary for the current OS
# - builds a docker image (if docker found)
# - collects artifacts under release/<version>/

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f VERSION ]; then
  echo "VERSION file not found"
  exit 1
fi
VERSION=$(cat VERSION)
echo "Building release for version: $VERSION"

API_DIR="$ROOT_DIR/apps/api"

echo "==> Building python distributions"
(
  cd "$API_DIR"
  uv build
)

echo "==> Creating SHA256SUMS"
mkdir -p "$API_DIR/dist"
(
  cd "$API_DIR"
  uv run python - <<PY > dist/SHA256SUMS
import hashlib,glob,os
files=sorted([f for f in glob.glob('dist/*') if os.path.isfile(f)])
for p in files:
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    print(f"{h}  {os.path.basename(p)}")
PY
)

echo "==> Building PyInstaller single-file (current OS)"
if [ -f "$API_DIR/app/main.py" ]; then
  # Use our custom hooks directory so package data like fake_useragent's
  # browsers.jsonl get included in the bundle.
  (
    cd "$API_DIR"
    uv run pyinstaller --additional-hooks-dir hooks --onefile app/main.py --name anibridge
  )
  PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
  mkdir -p "release/${VERSION}/${PLATFORM}"
  if [ -f "$API_DIR/dist/anibridge" ]; then
    cp "$API_DIR/dist/anibridge" "release/${VERSION}/${PLATFORM}/"
  elif [ -f "$API_DIR/dist/anibridge.exe" ]; then
    cp "$API_DIR/dist/anibridge.exe" "release/${VERSION}/${PLATFORM}/"
  else
    echo "PyInstaller did not produce expected binary in apps/api/dist/ (ok to continue)."
  fi
else
  echo "No apps/api/app/main.py entrypoint found — skipping PyInstaller step."
fi

if command -v docker >/dev/null 2>&1; then
  echo "==> Building Docker image"
  REMOTE=$(git config --get remote.origin.url || true)
  if [ -n "$REMOTE" ]; then
    IMAGE=$(echo "$REMOTE" | sed -E 's#.*[:/](.+/.+)(\.git)?#ghcr.io/\1#')
  else
    IMAGE="ghcr.io/zzackllack/anibridge"
  fi
  docker build -f apps/api/Dockerfile -t ${IMAGE}:${VERSION} -t ${IMAGE}:v${VERSION} . || echo "docker build failed"
else
  echo "docker not found — skipping docker build"
fi

echo "==> Collecting artifacts into release/${VERSION}/dist"
mkdir -p "release/${VERSION}/dist"
cp -f "$API_DIR"/dist/* "release/${VERSION}/dist/" || true

echo "Done. Artifacts are in: release/${VERSION}/"
echo " - Python dists: release/${VERSION}/dist/"
echo " - PyInstaller binary (if built): release/${VERSION}/<platform>/"

exit 0
