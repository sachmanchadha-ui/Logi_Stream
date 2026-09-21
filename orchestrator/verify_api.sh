#!/usr/bin/env bash
# D2-T2 verify for the orchestrator HTTP API (CLAUDE.md section 9).
#   bash orchestrator/verify_api.sh
#
# The centrepiece is the restart test: the conversation must survive uvicorn
# being killed, because that is the claim PostgresSaver exists to make and the
# beat the demo leans on when the human refreshes the page on stage.
#
# Costs a handful of free-tier LLM calls (F1 + F2 + F3), so it takes a minute or
# two. Judge0 is not involved at all.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && { set -a; . ./.env; set +a; }

BASE="http://localhost:8001"
TOKEN="${INTERNAL_TOKEN:-dev-internal-token-change-me}"
LOG="$ROOT/demo/logs/orchestrator-verify.log"
THREAD="verify-$(date +%s)"
PY=python; command -v python >/dev/null 2>&1 || PY=python3

pass=0; fail=0
ok() { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
no() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

UVICORN_PID=""

# $! gives the MSYS subshell pid, which is NOT the windows process holding the
# port -- killing it leaves uvicorn running and the restart test silently passes
# against a server that never died. Ask windows who owns the port instead.
listener_pid() {
  powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r' | head -1
}

start_uvicorn() {
  mkdir -p "$ROOT/demo/logs"
  ( cd "$ROOT/orchestrator" && nohup uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 >> "$LOG" 2>&1 & )
  for _ in $(seq 1 45); do
    curl -sf --max-time 2 "$BASE/health" >/dev/null 2>&1 && { UVICORN_PID=$(listener_pid); return 0; }
    sleep 1
  done
  return 1
}

api() {  # api <method> <path> [json-body] -> body to /tmp/ls_api.json, prints status
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -s --max-time 300 -o /tmp/ls_api.json -w '%{http_code}' \
      -X "$method" "$BASE$path" -H 'Content-Type: application/json' \
      -H "X-Internal-Token: $TOKEN" -H "X-Trace-Id: $THREAD-trace" -d "$body"
  else
    curl -s --max-time 300 -o /tmp/ls_api.json -w '%{http_code}' \
      -X "$method" "$BASE$path" -H "X-Internal-Token: $TOKEN" -H "X-Trace-Id: $THREAD-trace"
  fi
}

# NOTE: the json path must be passed as an ARGUMENT, not embedded in the -c
# string. MSYS rewrites /tmp/... into a Windows path only for argv, so a path
# baked into the source is handed to native python verbatim and does not exist.
field() { $PY -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for k in sys.argv[2].split('.'):
    d = d.get(k) if isinstance(d,dict) else None
# always json, so a JSON null prints as 'null' and not as python's 'None'
print(d if isinstance(d,str) else json.dumps(d))
" /tmp/ls_api.json "$1" 2>/dev/null; }

fixture() { $PY -c "
import json,sys
print(json.dumps({'type': sys.argv[1], 'text': open(sys.argv[2],encoding='utf-8').read()}))
" "$1" "$ROOT/demo/fixtures/$2"; }

echo "=== D2-T2 verify: orchestrator API ==="
echo "  thread: $THREAD"
echo

if ! curl -sf --max-time 3 "$BASE/health" >/dev/null 2>&1; then
  echo "starting uvicorn (log: ${LOG#$ROOT/})"
  start_uvicorn || { echo "uvicorn never became healthy"; tail -30 "$LOG"; exit 1; }
fi

# ------------------------------------------------------------------ auth

echo "[auth]"
CODE=$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$BASE/sessions/$THREAD")
[ "$CODE" = "401" ] && ok "GET /sessions/... without a token -> 401" \
                    || no "without a token -> $CODE (expected 401)"

CODE=$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' \
  -H 'X-Internal-Token: nope' "$BASE/sessions/$THREAD")
[ "$CODE" = "401" ] && ok "GET /sessions/... with a wrong token -> 401" \
                    || no "wrong token -> $CODE (expected 401)"

CODE=$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "$BASE/health")
[ "$CODE" = "200" ] && ok "GET /health needs no token -> 200" || no "/health -> $CODE"

# ---------------------------------------------------------------- lifecycle

echo
echo "[session lifecycle]"
CODE=$(api POST "/sessions/$THREAD/start" '{"problem_id":"two-sum","user_id":"demo-user"}')
if [ "$CODE" = "200" ]; then
  ok "start -> 200 (phase=$(field phase) status=$(field status))"
else
  no "start -> $CODE $(head -c 200 /tmp/ls_api.json)"
fi

[ "$(field last_eval)" = "null" ] && ok "last_eval is null before any evaluation" \
                                  || no "last_eval should be null, got $(field last_eval)"
[ "$(field last_execution)" = "null" ] && ok "last_execution is null before any run" \
                                       || no "last_execution should be null"

echo
echo "[event validation]"
CODE=$(api POST "/sessions/$THREAD/event" '{"type":"code","text":"print(1)"}')
[ "$CODE" = "409" ] && ok "code event in phase LOGIC -> 409" || no "code in LOGIC -> $CODE (expected 409)"

CODE=$(api POST "/sessions/$THREAD/event" '{"type":"logic","text":"   "}')
[ "$CODE" = "422" ] && ok "whitespace-only text -> 422" || no "empty text -> $CODE (expected 422)"

CODE=$(api POST "/sessions/nonexistent-thread/event" '{"type":"logic","text":"hello"}')
[ "$CODE" = "404" ] && ok "event on an unknown session -> 404" || no "unknown session -> $CODE"

# ------------------------------------------------------------- conversation

echo
echo "[conversation: F1 then F2]"
CODE=$(api POST "/sessions/$THREAD/event" "$(fixture logic logic_f1.txt)")
if [ "$CODE" = "200" ]; then
  V=$(field last_eval.verdict); M=$(field last_eval.misconception_id)
  [ "$V" = "FAIL" ] && ok "F1 -> verdict FAIL (misconception=$M)" || no "F1 verdict=$V (expected FAIL)"
else
  no "F1 -> $CODE $(head -c 200 /tmp/ls_api.json)"
fi

CODE=$(api POST "/sessions/$THREAD/event" "$(fixture chat chat_f2.txt)")
[ "$CODE" = "200" ] && ok "F2 chat -> 200" || no "F2 -> $CODE"

BEFORE=$(field messages | $PY -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "  ($BEFORE messages in the transcript before the restart)"

# ------------------------------------------------------ the restart test

echo
echo "[persistence: kill uvicorn and restart it]"
PID=$(listener_pid)

if [ -n "$PID" ]; then
  echo "  killing the process holding port 8001 (pid $PID)"
  taskkill //PID "$PID" //F //T >/dev/null 2>&1 || kill -9 "$PID" 2>/dev/null
  sleep 4
  curl -sf --max-time 2 "$BASE/health" >/dev/null 2>&1 \
    && no "uvicorn is still answering after the kill" \
    || ok "uvicorn is down"
  echo "  restarting uvicorn..."
  start_uvicorn || { echo "uvicorn did not come back"; tail -30 "$LOG"; exit 1; }
  ok "uvicorn is back up"
else
  no "could not find the uvicorn pid to kill (restart test skipped)"
fi

CODE=$(api GET "/sessions/$THREAD")
if [ "$CODE" = "200" ]; then
  AFTER=$(field messages | $PY -c "import json,sys; print(len(json.load(sys.stdin)))")
  if [ "$AFTER" = "$BEFORE" ]; then
    ok "conversation survived the restart ($AFTER messages, verdict=$(field last_eval.verdict))"
  else
    no "message count changed across the restart: $BEFORE -> $AFTER"
  fi
else
  no "GET after restart -> $CODE"
fi

# ------------------------------------------------------------ phase change

echo
echo "[F3: pass the gate]"
CODE=$(api POST "/sessions/$THREAD/event" "$(fixture logic logic_f3.txt)")
if [ "$CODE" = "200" ]; then
  V=$(field last_eval.verdict); P=$(field phase)
  { [ "$V" = "PASS" ] || [ "$V" = "FLAGGED" ]; } && [ "$P" = "CODE" ] \
    && ok "F3 -> $V, phase=$P, approach=$(field last_eval.matched_approach)" \
    || no "F3 verdict=$V phase=$P (wanted PASS/CODE)"
  [ "$(field accepted_logic)" != "null" ] && ok "accepted_logic is populated" \
                                          || no "accepted_logic is still null"
else
  no "F3 -> $CODE"
fi

CODE=$(api POST "/sessions/$THREAD/event" '{"type":"logic","text":"another approach"}')
[ "$CODE" = "409" ] && ok "logic event in phase CODE -> 409" || no "logic in CODE -> $CODE (expected 409)"

# ------------------------------------------------------------------- reset

echo
echo "[reset]"
CODE=$(api POST "/sessions/$THREAD/reset")
[ "$CODE" = "200" ] && ok "reset -> 200" || no "reset -> $CODE"

CODE=$(api GET "/sessions/$THREAD")
[ "$CODE" = "404" ] && ok "session is gone after reset -> 404" || no "after reset -> $CODE (expected 404)"

CODE=$(api POST "/sessions/$THREAD/start" '{"problem_id":"two-sum","user_id":"demo-user"}')
if [ "$CODE" = "200" ] && [ "$(field phase)" = "LOGIC" ] && [ "$(field last_eval)" = "null" ]; then
  ok "start after reset -> a fresh LOGIC session"
else
  no "start after reset -> $CODE phase=$(field phase) last_eval=$(field last_eval)"
fi

# --------------------------------------------------------------- trace id

echo
echo "[tracing]"
HDR=$(curl -s --max-time 30 -D - -o /dev/null -H "X-Internal-Token: $TOKEN" \
  -H "X-Trace-Id: probe-trace-123" "$BASE/sessions/$THREAD" | tr -d '\r' | grep -i '^x-trace-id:')
echo "$HDR" | grep -qi 'probe-trace-123' \
  && ok "X-Trace-Id is echoed back ($HDR)" || no "trace id not echoed: '$HDR'"
grep -q 'probe-trace-123' "$LOG" 2>/dev/null \
  && ok "X-Trace-Id appears in the orchestrator log" || no "trace id missing from the log"

echo
echo "=== D2-T2 VERIFY: $pass passed, $fail failed ==="
exit "$fail"
