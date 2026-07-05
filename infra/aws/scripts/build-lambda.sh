#!/usr/bin/env bash
# RelayGuard Lambda package build (shared by deploy scripts)
set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD_DIR="$ROOT/infra/aws/build"
PACKAGE_DIR="$BUILD_DIR/package"
ZIP_PATH="$BUILD_DIR/lambda.zip"
REQ_FILE="$ROOT/infra/aws/lambda_worker/requirements.txt"
HANDLER_FILE="$ROOT/infra/aws/lambda_worker/handler.py"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

echo "==> Cleaning build directory"
rm -rf "$PACKAGE_DIR" "$ZIP_PATH"
mkdir -p "$PACKAGE_DIR"

echo "==> Installing Lambda dependencies (Linux x86_64 for AWS Lambda)"
"$PYTHON" -m pip install -r "$REQ_FILE" -t "$PACKAGE_DIR" --upgrade --quiet \
  --platform manylinux2014_x86_64 \
  --python-version 3.12 \
  --implementation cp \
  --only-binary=:all:

echo "==> Copying RelayGuard sources"
cp "$HANDLER_FILE" "$PACKAGE_DIR/handler.py"
cp -R "$ROOT/relayguard" "$PACKAGE_DIR/"
cp -R "$ROOT/workers" "$PACKAGE_DIR/"
if [[ -d "$ROOT/infra/aws/lambda_worker/certs" ]]; then
  cp -R "$ROOT/infra/aws/lambda_worker/certs" "$PACKAGE_DIR/"
fi

echo "==> Creating zip: $ZIP_PATH"
(
  cd "$PACKAGE_DIR"
  if command -v zip >/dev/null 2>&1; then
    zip -qr "$ZIP_PATH" .
  else
    "$PYTHON" - <<'PY'
import pathlib
import zipfile

package = pathlib.Path(".")
zip_path = pathlib.Path(__import__("os").environ["ZIP_PATH"])
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in package.rglob("*"):
        if path.is_file():
            zf.write(path, path.relative_to(package).as_posix())
PY
  fi
)

echo "Lambda package ready: $ZIP_PATH"
