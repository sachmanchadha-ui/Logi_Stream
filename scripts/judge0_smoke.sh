#!/usr/bin/env bash
# D1-T1 smoke test for the HOSTED Judge0 CE API (CLAUDE.md sections 0.1, 8).
#
#   bash scripts/judge0_smoke.sh
#
# Reads JUDGE0_* from the environment (source .env first). Does exactly one
# /languages call, one batch submit and at most JUDGE0_MAX_POLLS polls, then
# prints how many Judge0 requests it consumed -- quota is finite and every
# submit AND every poll is billed (trap 1).
#
# jq is not installed on this box, so JSON is handled with python.
set -uo pipefail

if [ -f "$(dirname "${BASH_SOURCE[0]}")/../.env" ] && [ -z "${JUDGE0_RAPIDAPI_KEY:-}" ]; then
  set -a; . "$(dirname "${BASH_SOURCE[0]}")/../.env"; set +a
fi

JUDGE0_URL="${JUDGE0_URL:-https://judge0-ce.p.rapidapi.com}"
JUDGE0_RAPIDAPI_HOST="${JUDGE0_RAPIDAPI_HOST:-judge0-ce.p.rapidapi.com}"
JUDGE0_POLL_INTERVAL_MS="${JUDGE0_POLL_INTERVAL_MS:-1000}"
JUDGE0_MAX_POLLS="${JUDGE0_MAX_POLLS:-15}"
EXPECT_LANGUAGE_ID="${JUDGE0_PYTHON_LANGUAGE_ID:-71}"

if [ -z "${JUDGE0_RAPIDAPI_KEY:-}" ]; then
  echo "STOP: JUDGE0_RAPIDAPI_KEY is not set."
  echo "      Subscribe to Judge0 CE on RapidAPI, then put the key in .env."
  exit 2
fi

PY=python
command -v python >/dev/null 2>&1 || PY=python3

REQUESTS=0
say() { printf '%s\n' "$*"; }

api() {  # api <method> <path-with-query> [body-file]
  local method="$1" path="$2" body="${3:-}"
  REQUESTS=$((REQUESTS + 1))
  if [ -n "$body" ]; then
    curl -sS --max-time 60 -X "$method" "${JUDGE0_URL}${path}" \
      -H "Content-Type: application/json" \
      -H "X-RapidAPI-Key: ${JUDGE0_RAPIDAPI_KEY}" \
      -H "X-RapidAPI-Host: ${JUDGE0_RAPIDAPI_HOST}" \
      --data-binary "@${body}"
  else
    curl -sS --max-time 60 -X "$method" "${JUDGE0_URL}${path}" \
      -H "X-RapidAPI-Key: ${JUDGE0_RAPIDAPI_KEY}" \
      -H "X-RapidAPI-Host: ${JUDGE0_RAPIDAPI_HOST}"
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

say "=== Judge0 hosted smoke test ==="
say "  endpoint : $JUDGE0_URL"
say ""

# ---------------------------------------------------------------- 1. languages
say "[1/3] GET /languages -- confirming the Python 3 language id"
api GET "/languages" > "$TMP/languages.json" || { say "  FAIL: request error"; exit 1; }

LANG_ID=$($PY - "$TMP/languages.json" "$EXPECT_LANGUAGE_ID" <<'PYEOF'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
expect = int(sys.argv[2])
try:
    langs = json.loads(raw)
except Exception:
    print("ERR " + raw[:300].replace("\n", " "))
    raise SystemExit(0)
if isinstance(langs, dict):                      # error payload, e.g. 401/403
    print("ERR " + json.dumps(langs)[:300])
    raise SystemExit(0)
pys = [l for l in langs if "python" in l["name"].lower()]
for l in pys:
    print("INFO   id=%-4s %s" % (l["id"], l["name"]), file=sys.stderr)
hit = [l for l in pys if l["id"] == expect]
if hit:
    print(expect)
else:
    py3 = sorted([l for l in pys if "(3." in l["name"]], key=lambda l: l["id"])
    print(("FOUND %d" % py3[-1]["id"]) if py3 else "ERR no python 3 language offered")
PYEOF
)

case "$LANG_ID" in
  ERR*)   say "  FAIL: ${LANG_ID#ERR }"
          say "        401/403 here means the key is wrong or not subscribed to Judge0 CE."
          say "        Judge0 requests used: $REQUESTS"
          exit 1 ;;
  FOUND*) say "  WARN: JUDGE0_PYTHON_LANGUAGE_ID=$EXPECT_LANGUAGE_ID is not offered."
          say "        This listing offers ${LANG_ID#FOUND } -- update .env before continuing."
          LANG_ID="${LANG_ID#FOUND }" ;;
  *)      say "  OK: language id $LANG_ID confirmed" ;;
esac

# ------------------------------------------------------------------- 2. submit
say ""
say "[2/3] POST /submissions/batch -- one submission, base64 in both directions"

$PY - "$TMP/req.json" "$LANG_ID" <<'PYEOF'
import base64, json, sys
src = 'print("hello")\n'
body = {"submissions": [{
    "language_id": int(sys.argv[2]),
    "source_code": base64.b64encode(src.encode()).decode(),
    "stdin": base64.b64encode(b"").decode(),
    "cpu_time_limit": 2,
    "wall_time_limit": 5,
    "memory_limit": 128000,
}]}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(body))
PYEOF

api POST "/submissions/batch?base64_encoded=true" "$TMP/req.json" > "$TMP/submit.json" \
  || { say "  FAIL: request error"; exit 1; }

TOKENS=$($PY - "$TMP/submit.json" <<'PYEOF'
import json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
try:
    data = json.loads(raw)
except Exception:
    print("ERR " + raw[:300].replace("\n", " ")); raise SystemExit(0)
if isinstance(data, dict):
    print("ERR " + json.dumps(data)[:300]); raise SystemExit(0)
toks = [d.get("token") for d in data if d.get("token")]
print(",".join(toks) if toks else "ERR " + json.dumps(data)[:300])
PYEOF
)

case "$TOKENS" in
  ERR*) say "  FAIL: ${TOKENS#ERR }"; say "        Judge0 requests used: $REQUESTS"; exit 1 ;;
  *)    say "  OK: token(s) $TOKENS" ;;
esac

# --------------------------------------------------------------------- 3. poll
say ""
say "[3/3] GET /submissions/batch -- polling every ${JUDGE0_POLL_INTERVAL_MS}ms, max ${JUDGE0_MAX_POLLS}"

SLEEP_S=$($PY -c "import sys;print(int(sys.argv[1])/1000.0)" "$JUDGE0_POLL_INTERVAL_MS")
RESULT=""
for i in $(seq 1 "$JUDGE0_MAX_POLLS"); do
  sleep "$SLEEP_S"
  api GET "/submissions/batch?tokens=${TOKENS}&base64_encoded=true&fields=token,status_id,status,stdout,stderr,compile_output,time" \
    > "$TMP/poll.json" || { say "  FAIL: request error"; exit 1; }

  RESULT=$($PY - "$TMP/poll.json" <<'PYEOF'
import base64, json, sys
raw = open(sys.argv[1], encoding="utf-8").read()
try:
    data = json.loads(raw)
except Exception:
    print("ERR " + raw[:300].replace("\n", " ")); raise SystemExit(0)
subs = data.get("submissions") if isinstance(data, dict) else data
if not isinstance(subs, list):
    print("ERR " + json.dumps(data)[:300]); raise SystemExit(0)
s = subs[0]
sid = (s.get("status") or {}).get("id", s.get("status_id"))
if sid in (1, 2):
    print("PENDING %s" % sid); raise SystemExit(0)
def dec(v):
    if not v:
        return ""
    try:
        return base64.b64decode(v).decode("utf-8", "replace")
    except Exception:
        return v
print("DONE %s|%s|%s|%s" % (
    sid,
    (s.get("status") or {}).get("description", ""),
    dec(s.get("stdout")).strip(),
    (dec(s.get("stderr")) + dec(s.get("compile_output"))).strip().replace("\n", " ")[:200],
))
PYEOF
)
  case "$RESULT" in
    ERR*)     say "  FAIL: ${RESULT#ERR }"; say "        Judge0 requests used: $REQUESTS"; exit 1 ;;
    PENDING*) say "  poll $i: still ${RESULT#PENDING }" ;;
    DONE*)    say "  poll $i: finished"; break ;;
  esac
done

say ""
if [ "${RESULT:0:4}" != "DONE" ]; then
  say "FAIL: still queued after $JUDGE0_MAX_POLLS polls -> this is an INFRA_ERROR (section 8)"
  say "Judge0 requests used: $REQUESTS"
  exit 1
fi

PAYLOAD="${RESULT#DONE }"
STATUS_ID="${PAYLOAD%%|*}"; REST="${PAYLOAD#*|}"
STATUS_DESC="${REST%%|*}"; REST="${REST#*|}"
STDOUT="${REST%%|*}"; STDERR="${REST#*|}"

say "  status  : $STATUS_ID ($STATUS_DESC)"
say "  stdout  : '$STDOUT'"
[ -n "$STDERR" ] && say "  stderr  : $STDERR"
say ""

RC=0
[ "$STATUS_ID" = "3" ] || { say "ASSERT FAIL: expected status 3 (Accepted), got $STATUS_ID"; RC=1; }
[ "$STDOUT" = "hello" ] || { say "ASSERT FAIL: expected stdout 'hello', got '$STDOUT'"; RC=1; }

say "Judge0 requests used: $REQUESTS  (1 languages + 1 submit + $((REQUESTS - 2)) poll(s))"
say ""
[ "$RC" -eq 0 ] && say "JUDGE0 SMOKE: PASS" || say "JUDGE0 SMOKE: FAIL"
exit "$RC"
