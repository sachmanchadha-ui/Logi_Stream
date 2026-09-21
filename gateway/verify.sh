#!/usr/bin/env bash
# D2-T3 verify for the Rust gateway (CLAUDE.md section 9).
#   bash gateway/verify.sh
#
# Everything goes through port 8000 only -- that is the point. The browser never
# sees Python or Java, so if the flow works here it works from the UI.
#
# The security assertions are the ones that matter: a client that could choose
# its own thread_id could read anyone else's session.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && { set -a; . ./.env; set +a; }
. scripts/env.sh

BASE="http://localhost:8000"
LOG="$ROOT/demo/logs/gateway-verify.log"
PY=python; command -v python >/dev/null 2>&1 || PY=python3

pass=0; fail=0
ok() { printf '  PASS  %s\n' "$1"; pass=$((pass+1)); }
no() { printf '  FAIL  %s\n' "$1"; fail=$((fail+1)); }

listener_pid() {
  powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r' | head -1
}

STARTED_BY_US=0
cleanup() {
  if [ "$STARTED_BY_US" = "1" ]; then
    PID=$(listener_pid)
    [ -n "$PID" ] && { echo; echo "stopping the gateway we started (pid $PID)"; \
      taskkill //PID "$PID" //F //T >/dev/null 2>&1; }
  fi
}
trap cleanup EXIT

field() { $PY -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for k in sys.argv[2].split('.'):
    d = d.get(k) if isinstance(d,dict) else None
print(d if isinstance(d,str) else json.dumps(d))
" /tmp/ls_gw.json "$1" 2>/dev/null; }

fixture() { $PY -c "
import json,sys
print(json.dumps({'problem_id':'two-sum','type':sys.argv[1],
                  'text':open(sys.argv[2],encoding='utf-8').read()}))
" "$1" "$ROOT/demo/fixtures/$2"; }

echo "=== D2-T3 verify: Rust gateway ==="
echo

# ------------------------------------------------------------ prerequisites

for svc in "8080 domain (java)" "8001 orchestrator (python)"; do
  port="${svc%% *}"; name="${svc#* }"
  if curl -sf --max-time 3 "http://localhost:$port/health" >/dev/null 2>&1; then
    echo "  upstream ok: $name on :$port"
  else
    echo "  STOP: $name is not running on :$port - start it first"
    exit 2
  fi
done
echo

if ! curl -sf --max-time 3 "$BASE/health" >/dev/null 2>&1; then
  BIN="$ROOT/gateway/target/release/logistream-gateway.exe"
  [ -x "$BIN" ] || BIN="$ROOT/gateway/target/release/logistream-gateway"
  if [ ! -x "$BIN" ]; then
    echo "  building the gateway..."
    ( cd "$ROOT/gateway" && cargo build --release ) || { echo "BUILD FAILED"; exit 1; }
  fi
  mkdir -p "$ROOT/demo/logs"
  echo "  starting the gateway (log: ${LOG#$ROOT/})"
  ( cd "$ROOT/gateway" && nohup "$BIN" >> "$LOG" 2>&1 & )
  STARTED_BY_US=1
  for _ in $(seq 1 30); do
    curl -sf --max-time 2 "$BASE/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf --max-time 2 "$BASE/health" >/dev/null 2>&1 || {
    echo "  gateway never became healthy:"; tail -20 "$LOG"; exit 1; }
  echo "  gateway is up"
fi
echo

# -------------------------------------------------------------------- basics

echo "[routing]"
CODE=$(curl -s --max-time 10 -o /tmp/ls_gw.json -w '%{http_code}' "$BASE/health")
[ "$CODE" = "200" ] && ok "GET /health -> 200" || no "GET /health -> $CODE"

CODE=$(curl -s --max-time 20 -o /tmp/ls_gw.json -w '%{http_code}' "$BASE/api/problems/two-sum")
if [ "$CODE" = "200" ]; then
  ok "GET /api/problems/two-sum -> 200 (proxied to java)"
  RES=$($PY - /tmp/ls_gw.json <<'PYEOF'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
d = json.loads(raw)
bad = []
for leaked in ("rubric", "harness_python", "tests"):
    if leaked in d: bad.append("leaks " + leaked)
for term in ("socratic_counter", "forbidden_terms", "expected_output"):
    if term in raw: bad.append("body contains " + term)
if d.get("language") != "python": bad.append("language=%r" % d.get("language"))
print("OK" if not bad else "BAD " + "; ".join(bad))
PYEOF
)
  [ "$RES" = "OK" ] && ok "  ...still carries no rubric or hidden tests" || no "  ...${RES#BAD }"
else
  no "GET /api/problems/two-sum -> $CODE"
fi

# ------------------------------------------------------- thread derivation

echo
echo "[identity: the client must not be able to choose its thread]"

curl -s --max-time 30 -o /tmp/ls_gw.json -X POST "$BASE/api/sessions/start" \
  -H 'Content-Type: application/json' -d '{"problem_id":"two-sum"}' >/dev/null
BASELINE=$(field thread_id)
[ -n "$BASELINE" ] && [ "$BASELINE" != "null" ] \
  && ok "start -> thread_id derived server-side (${BASELINE:0:16}...)" \
  || no "no thread_id in the start response"

EXPECTED=$($PY -c "
import hashlib,sys
print(hashlib.sha256(('%s:%s' % (sys.argv[1], sys.argv[2])).encode()).hexdigest())
" "${DEMO_USER_ID:-demo-user}" "two-sum")
[ "$BASELINE" = "$EXPECTED" ] \
  && ok "thread_id == sha256(user_id + ':' + problem_id)" \
  || no "derivation mismatch: got $BASELINE expected $EXPECTED"

# a body field named thread_id must be ignored outright
curl -s --max-time 30 -o /tmp/ls_gw.json -X POST "$BASE/api/sessions/start" \
  -H 'Content-Type: application/json' \
  -d '{"problem_id":"two-sum","thread_id":"attacker"}' >/dev/null
GOT=$(field thread_id)
[ "$GOT" = "$BASELINE" ] && ok 'a "thread_id":"attacker" body field is ignored' \
                         || no "body thread_id changed the session: $GOT"

# ...and so must a header
curl -s --max-time 30 -o /tmp/ls_gw.json -X POST "$BASE/api/sessions/start" \
  -H 'Content-Type: application/json' -H 'X-Thread-Id: attacker' \
  -d '{"problem_id":"two-sum"}' >/dev/null
GOT=$(field thread_id)
[ "$GOT" = "$BASELINE" ] && ok "an X-Thread-Id: attacker header is ignored" \
                         || no "header thread_id changed the session: $GOT"

# a different user gets a different, independent session
curl -s --max-time 30 -o /tmp/ls_gw.json -X POST "$BASE/api/sessions/start" \
  -H 'Content-Type: application/json' -H 'X-Demo-User: someone-else' \
  -d '{"problem_id":"two-sum"}' >/dev/null
OTHER=$(field thread_id)
[ -n "$OTHER" ] && [ "$OTHER" != "$BASELINE" ] \
  && ok "X-Demo-User: someone-else gets a different thread (${OTHER:0:16}...)" \
  || no "a different user did not get a different thread"
[ "$(field last_eval)" = "null" ] && ok "  ...and that session is empty" \
                                  || no "  ...but it is not empty"

# ------------------------------------------------------------------ tracing

echo
echo "[tracing]"
HDR=$(curl -s --max-time 20 -D - -o /dev/null -H 'X-Trace-Id: gw-probe-999' \
  "$BASE/api/problems/two-sum" | tr -d '\r' | grep -i '^x-trace-id:')
echo "$HDR" | grep -qi 'gw-probe-999' && ok "X-Trace-Id is propagated and echoed" \
                                      || no "trace id not echoed: '$HDR'"

GEN=$(curl -s --max-time 20 -D - -o /dev/null "$BASE/api/problems/two-sum" \
  | tr -d '\r' | grep -i '^x-trace-id:' | awk '{print $2}')
[ -n "$GEN" ] && ok "a request with no trace id gets one generated ($GEN)" \
              || no "no trace id generated"

echo "  checking the same id reached the downstream logs..."
curl -s --max-time 60 -o /dev/null -H 'X-Trace-Id: cross-service-777' \
  "$BASE/api/problems/two-sum"
sleep 1
FOUND=0
grep -q 'cross-service-777' "$LOG" 2>/dev/null && FOUND=$((FOUND+1))
grep -q 'cross-service-777' "$ROOT/demo/logs/domain.log" 2>/dev/null && FOUND=$((FOUND+1))
[ "$FOUND" -ge 2 ] && ok "the same trace id appears in gateway AND java logs" \
                   || no "trace id found in only $FOUND/2 logs"

# ------------------------------------------------------------- upstream errors

echo
echo "[error passthrough]"
CODE=$(curl -s --max-time 30 -o /tmp/ls_gw.json -w '%{http_code}' \
  -X POST "$BASE/api/sessions/event" -H 'Content-Type: application/json' \
  -d '{"problem_id":"two-sum","type":"code","text":"print(1)"}')
[ "$CODE" = "409" ] && ok "python's 409 is passed through, not flattened to 500" \
                    || no "code-in-LOGIC through the gateway -> $CODE (expected 409)"

CODE=$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' \
  -X POST "$BASE/api/sessions/event" -H 'Content-Type: application/json' \
  -d '{"problem_id":"two-sum","type":"logic","text":"   "}')
[ "$CODE" = "422" ] && ok "python's 422 is passed through" || no "empty text -> $CODE"

CODE=$(curl -s --max-time 20 -o /dev/null -w '%{http_code}' "$BASE/api/problems/does-not-exist")
[ "$CODE" = "404" ] && ok "java's 404 is passed through" || no "unknown problem -> $CODE"

# ---------------------------------------------------------------------- CORS

echo
echo "[CORS]"
PRE=$(curl -s --max-time 10 -D - -o /dev/null -X OPTIONS "$BASE/api/sessions/event" \
  -H "Origin: ${CORS_ORIGIN:-http://localhost:3000}" \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: content-type' | tr -d '\r')
echo "$PRE" | grep -qi 'access-control-allow-origin' \
  && ok "preflight for a JSON POST is allowed" \
  || no "preflight has no access-control-allow-origin (trap 6)"
# Access-Control-Expose-Headers is returned on the ACTUAL response, not on the
# preflight, so it has to be checked with a real GET.
ACT=$(curl -s --max-time 20 -D - -o /dev/null "$BASE/api/problems/two-sum" \
  -H "Origin: ${CORS_ORIGIN:-http://localhost:3000}" | tr -d '\r')
echo "$ACT" | grep -qi "access-control-expose-headers:.*x-trace-id" \
  && ok "x-trace-id is exposed to the browser on real responses" \
  || no "expose-headers missing: $(echo "$ACT" | grep -i expose || echo none)"

# ------------------------------------------------------------- the real flow

echo
echo "[end-to-end through port 8000 only]"
curl -s --max-time 30 -o /dev/null -X POST "$BASE/api/sessions/reset" \
  -H 'Content-Type: application/json' -d '{"problem_id":"two-sum"}'
curl -s --max-time 30 -o /tmp/ls_gw.json -X POST "$BASE/api/sessions/start" \
  -H 'Content-Type: application/json' -d '{"problem_id":"two-sum"}' >/dev/null

t0=$(date +%s)
CODE=$(curl -s --max-time 300 -o /tmp/ls_gw.json -w '%{http_code}' \
  -X POST "$BASE/api/sessions/event" -H 'Content-Type: application/json' \
  -d "$(fixture logic logic_f1.txt)")
t1=$(date +%s)
if [ "$CODE" = "200" ]; then
  V=$(field last_eval.verdict)
  [ "$V" = "FAIL" ] && ok "F1 through the gateway -> FAIL in $((t1-t0))s (misconception=$(field last_eval.misconception_id))" \
                    || no "F1 -> verdict $V"
  [ "$(field debug.trace_id)" != "null" ] && ok "  ...and the view carries debug.trace_id" \
                                          || no "  ...but debug.trace_id is null"
else
  no "F1 through the gateway -> $CODE"
fi

CODE=$(curl -s --max-time 20 -o /tmp/ls_gw.json -w '%{http_code}' "$BASE/api/sessions/two-sum")
[ "$CODE" = "200" ] && [ "$(field last_eval.verdict)" = "FAIL" ] \
  && ok "GET /api/sessions/two-sum resumes the same session" \
  || no "resume -> $CODE verdict=$(field last_eval.verdict)"

echo
echo "=== D2-T3 VERIFY: $pass passed, $fail failed ==="
exit "$fail"
