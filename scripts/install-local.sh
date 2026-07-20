#!/usr/bin/env bash
set -euo pipefail

# Install Nagient directly into a virtual environment. This path deliberately
# does not inspect or invoke Docker; the runtime is a normal Python process.
SOURCE_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_WORKSPACE_ROOT="${NAGIENT_WORKSPACE_ROOT:-$NAGIENT_HOME/workspace}"
PYTHON_BIN="${NAGIENT_PYTHON:-}"
START_RUNTIME="true"

usage() {
  cat <<'EOF'
Usage: install-local.sh [options]

Options:
  --home <path>       Runtime directory (default: ~/.nagient)
  --source <path>     Nagient checkout or package directory
  --python <path>     Python 3.11+ interpreter
  --no-start          Install files without starting the background runtime
  -h, --help          Show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --home) NAGIENT_HOME="${2:?--home requires a path}"; shift 2 ;;
    --source) SOURCE_ROOT="$(CDPATH= cd -- "${2:?--source requires a path}" && pwd)"; shift 2 ;;
    --python) PYTHON_BIN="${2:?--python requires an interpreter}"; shift 2 ;;
    --no-start) START_RUNTIME="false"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$PYTHON_BIN" ]; then
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON_BIN="$candidate"; break; fi
  done
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3.11 or newer is required. Docker is not used by this installer." >&2
  exit 1
fi

version_ok="$("$PYTHON_BIN" -c 'import sys; print(int(sys.version_info >= (3, 11)))')"
if [ "$version_ok" != "1" ]; then
  echo "Python 3.11 or newer is required ($("$PYTHON_BIN" --version 2>&1))." >&2
  exit 1
fi

mkdir -p "$NAGIENT_HOME"
VENV_DIR="$NAGIENT_HOME/venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
RUNTIME_PYTHON="$VENV_DIR/bin/python"
RUNTIME_PYTHONPATH=""
if [ -d "$SOURCE_ROOT/src/nagient" ]; then
  # A source checkout is already runnable; avoid network/build dependencies.
  RUNTIME_PYTHONPATH="$SOURCE_ROOT/src"
else
  "$RUNTIME_PYTHON" -m pip install --no-deps --quiet --upgrade "$SOURCE_ROOT"
fi

export NAGIENT_HOME NAGIENT_WORKSPACE_ROOT
if [ -n "$RUNTIME_PYTHONPATH" ]; then
  PYTHONPATH="$RUNTIME_PYTHONPATH" "$RUNTIME_PYTHON" -m nagient init --force --format json >/dev/null
else
  "$RUNTIME_PYTHON" -m nagient init --force --format json >/dev/null
fi

BIN_DIR="$NAGIENT_HOME/bin"
mkdir -p "$BIN_DIR" "$NAGIENT_HOME/logs"
cat >"$BIN_DIR/nagient" <<EOF
#!/usr/bin/env bash
set -euo pipefail
NAGIENT_HOME="\${NAGIENT_HOME:-$NAGIENT_HOME}"
NAGIENT_WORKSPACE_ROOT="\${NAGIENT_WORKSPACE_ROOT:-$NAGIENT_HOME/workspace}"
VENV_DIR="$VENV_DIR"
RUNTIME_PYTHONPATH="$RUNTIME_PYTHONPATH"
PID_FILE="$NAGIENT_HOME/state/runtime.pid"
LOG_FILE="$NAGIENT_HOME/logs/runtime.log"
mkdir -p "\$(dirname "\$PID_FILE")" "\$(dirname "\$LOG_FILE")"
if [ -n "\$RUNTIME_PYTHONPATH" ]; then export PYTHONPATH="\$RUNTIME_PYTHONPATH"; fi
export NAGIENT_HOME NAGIENT_WORKSPACE_ROOT
running() { [ -s "\$PID_FILE" ] && kill -0 "\$(cat "\$PID_FILE")" 2>/dev/null; }
start_runtime() {
  if running; then echo "Nagient is already running (pid \$(cat "\$PID_FILE"))."; return 0; fi
  nohup "$VENV_DIR/bin/python" -m nagient serve >>"\$LOG_FILE" 2>&1 &
  echo "\$!" >"\$PID_FILE"
  echo "Nagient started (pid \$!)."
}
stop_runtime() {
  if ! running; then rm -f "\$PID_FILE"; echo "Nagient is not running."; return 0; fi
  kill "\$(cat "\$PID_FILE")"; rm -f "\$PID_FILE"; echo "Nagient stopped."
}
case "\${1:-}" in
  up|start) start_runtime ;;
  down|stop) stop_runtime ;;
  restart) stop_runtime; start_runtime ;;
  ps|status) exec "$VENV_DIR/bin/python" -m nagient status "\${@:2}" ;;
  logs) exec tail -n "\${2:-80}" "\$LOG_FILE" ;;
  *) exec "$VENV_DIR/bin/python" -m nagient "\$@" ;;
esac
EOF
chmod +x "$BIN_DIR/nagient"

if [ "$START_RUNTIME" = "true" ]; then "$BIN_DIR/nagient" start; fi
echo "Nagient installed without Docker in $NAGIENT_HOME"
echo "Add $BIN_DIR to PATH, then run: nagient setup"
