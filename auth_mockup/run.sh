#!/usr/bin/env bash
# Run the isolated auth mockup on :8002.
#
#   bash auth_mockup/run.sh              foreground
#   bash auth_mockup/run.sh --background  detached, logs to demo/logs/auth_mockup.log
#
# Touches nothing the demo stack owns: different port, different .env, its own
# cargo target directory. Safe to start and stop while a demo is running.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/auth_mockup"

if [ ! -f .env ]; then
  echo "STOP: auth_mockup/.env is missing."
  echo "      cp auth_mockup/.env.example auth_mockup/.env  and add your Google credentials."
  echo "      (Do NOT put them in the repo-root .env - that belongs to the demo stack.)"
  exit 2
fi

# Loads OUR .env only. The root .env is never sourced here.
set -a; . ./.env; set +a
# MinGW linker + repo-pinned toolchain; see README "Linker".
. "$ROOT/scripts/env.sh"

PORT="${AUTH_MOCKUP_PORT:-8002}"

# refuse to collide with the demo stack rather than fighting it for a port
case "$PORT" in
  3000|8000|8001|8080|4000|5432)
    echo "STOP: port $PORT belongs to the demo stack. Pick another AUTH_MOCKUP_PORT."
    exit 2 ;;
esac

held=$(powershell -NoProfile -Command \
  "(Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue).OwningProcess" \
  2>/dev/null | tr -d '\r' | head -1)
if [ -n "$held" ]; then
  echo "note: port $PORT is already held by pid $held - stop it first if that is an old copy."
fi

BIN="$ROOT/auth_mockup/target/release/logistream-auth-mockup.exe"
[ -x "$BIN" ] || BIN="$ROOT/auth_mockup/target/release/logistream-auth-mockup"
if [ ! -x "$BIN" ]; then
  echo "building (first run only)..."
  cargo build --release || { echo "cargo build failed"; exit 1; }
fi

if [ "${1:-}" = "--background" ]; then
  mkdir -p "$ROOT/demo/logs"
  ( nohup "$BIN" > "$ROOT/demo/logs/auth_mockup.log" 2>&1 < /dev/null & )
  for _ in $(seq 1 25); do
    curl -sf --max-time 2 "http://localhost:$PORT/health" >/dev/null 2>&1 && {
      echo "auth mockup up on http://localhost:$PORT"
      echo "  log: demo/logs/auth_mockup.log"
      exit 0; }
    sleep 1
  done
  echo "it did not become healthy; last log lines:"
  tail -20 "$ROOT/demo/logs/auth_mockup.log"
  exit 1
fi

echo "auth mockup starting on http://localhost:$PORT  (ctrl-c to stop)"
exec "$BIN"
