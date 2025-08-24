#!/usr/bin/env bash
set -euo pipefail

# Local release build helper
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

# choose python
if [ -x ".venv/bin/python" ]; then
  PYTHON=.venv/bin/python
else
  PYTHON=$(command -v python3 || command -v python)
fi
echo "Using python: $PYTHON"

echo "==> Building python distributions"
$PYTHON -m pip install --upgrade build >/dev/null
$PYTHON -m build

echo "==> Creating SHA256SUMS"
$PYTHON - <<PY > dist/SHA256SUMS
import hashlib,glob,os
files=sorted([f for f in glob.glob('dist/*') if os.path.isfile(f)])
for p in files:
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    print(f"{h}  {os.path.basename(p)}")
PY

echo "==> Building PyInstaller single-file (current OS)"
$PYTHON -m pip install --upgrade pyinstaller >/dev/null
if [ -f app/main.py ]; then
  $PYTHON -m PyInstaller --onefile app/main.py --name anibridge
  PLATFORM=$(uname -s | tr '[:upper:]' '[:lower:]')
  mkdir -p "release/${VERSION}/${PLATFORM}"
  if [ -f dist/anibridge ]; then
    cp dist/anibridge "release/${VERSION}/${PLATFORM}/"
  elif [ -f dist/anibridge.exe ]; then
    cp dist/anibridge.exe "release/${VERSION}/${PLATFORM}/"
  else
    echo "PyInstaller did not produce expected binary in dist/ (ok to continue)."
  fi
else
  echo "No app/main.py entrypoint found — skipping PyInstaller step."
fi

if command -v docker >/dev/null 2>&1; then
  echo "==> Building Docker image"
  REMOTE=$(git config --get remote.origin.url || true)
  if [ -n "$REMOTE" ]; then
    IMAGE=$(echo "$REMOTE" | sed -E 's#.*[:/](.+/.+)(\.git)?#ghcr.io/\1#')
  else
    IMAGE="ghcr.io/youruser/anibridge"
  fi
  docker build -t ${IMAGE}:${VERSION} -t ${IMAGE}:v${VERSION} . || echo "docker build failed"
else
  echo "docker not found — skipping docker build"
fi

echo "==> Collecting artifacts into release/${VERSION}/dist"
mkdir -p "release/${VERSION}/dist"
cp -f dist/* "release/${VERSION}/dist/" || true

echo "Done. Artifacts are in: release/${VERSION}/"
echo " - Python dists: release/${VERSION}/dist/"
echo " - PyInstaller binary (if built): release/${VERSION}/<platform>/"

exit 0
