#!/usr/bin/env bash
# Drive the whole section 10 demo through the gateway and time every beat
# (CLAUDE.md D3-T5).
#
#   bash demo/rehearse.sh            the scripted run: F1 F2 F3 F4 F5
#   bash demo/rehearse.sh --backup   the Q&A fixtures too: F3b F4b F6
#
# This is the same path the browser takes -- port 8000 only, nothing internal --
# so a green run here means the UI will behave. Use it to check the stack after
# a restart without spending your own attention on clicking, and to see what the
# beat timings actually are once the caches are warm.
#
# It does NOT replace your own browser runs: it cannot see the chat panel
# opening, the stepper advancing, or the drawer rendering.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && { set -a; . ./.env; set +a; }

BASE="http://localhost:8000"
PROBLEM="two-sum"
PY=python; command -v python >/dev/null 2>&1 || PY=python3
BACKUP=0
[ "${1:-}" = "--backup" ] && BACKUP=1

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; RESET=$'\033[0m'

pass=0; fail=0
declare -a TIMINGS

post() {  # post <path> <json> -> body in /tmp/ls_reh.json, prints status
  curl -s --max-time 300 -o /tmp/ls_reh.json -w '%{http_code}' \
    -X POST "$BASE$1" -H 'Content-Type: application/json' -d "$2"
}

field() { $PY -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for k in sys.argv[2].split('.'):
    d = d.get(k) if isinstance(d,dict) else None
print(d if isinstance(d,str) else json.dumps(d))
" /tmp/ls_reh.json "$1" 2>/dev/null; }

body() {  # body <type> <fixture>
  $PY -c "
import json,sys
print(json.dumps({'problem_id':'two-sum','type':sys.argv[1],
                  'text':open(sys.argv[2],encoding='utf-8').read()}))
" "$1" "$ROOT/demo/fixtures/$2"
}

# beat <label> <type> <fixture> <what-to-check> <expected>
beat() {
  local label="$1" etype="$2" fixture="$3" check="$4" expected="$5"
  local t0 t1 code got

  t0=$(date +%s)
  code=$(post /api/sessions/event "$(body "$etype" "$fixture")")
  t1=$(date +%s)
  local secs=$((t1 - t0))
  TIMINGS+=("$label:$secs")

  if [ "$code" != "200" ]; then
    printf '  %sFAIL%s %-5s %3ss  HTTP %s  %s\n' "$RED" "$RESET" "$label" "$secs" "$code" \
      "$(head -c 120 /tmp/ls_reh.json)"
    fail=$((fail + 1)); return
  fi

  got=$(field "$check")
  if [ "$got" = "$expected" ]; then
    printf '  %sok  %s %-5s %3ss  %s=%s%s\n' "$GREEN" "$RESET" "$label" "$secs" "$check" "$got" \
      "$(extra)"
    pass=$((pass + 1))
  else
    printf '  %sFAIL%s %-5s %3ss  %s=%s (wanted %s)\n' "$RED" "$RESET" "$label" "$secs" \
      "$check" "$got" "$expected"
    fail=$((fail + 1))
  fi
}

extra() {  # a short trailing note: cache hits and regenerations are the interesting bits
  local hit regen fb
  hit=$(field last_eval.cache_hit); regen=$(field debug.regenerations); fb=$(field debug.fallback_used)
  local out=""
  [ "$hit" = "true" ] && out="$out ${DIM}cache${RESET}"
  [ "$regen" != "0" ] && [ -n "$regen" ] && out="$out ${YELLOW}regen=$regen${RESET}"
  [ "$fb" = "true" ] && out="$out ${YELLOW}fallback${RESET}"
  printf '%s' "$out"
}

fresh() {
  post /api/sessions/reset "{\"problem_id\":\"$PROBLEM\"}" >/dev/null
  post /api/sessions/start "{\"problem_id\":\"$PROBLEM\"}" >/dev/null
}

echo "${BOLD}LogiStream — scripted rehearsal${RESET}  ${DIM}via $BASE${RESET}"
if ! curl -sf --max-time 5 "$BASE/health" >/dev/null 2>&1; then
  echo "${RED}STOP: the gateway is not up. Run: bash demo/start.sh${RESET}"
  exit 2
fi
echo

T0=$(date +%s)
echo "${BOLD}the scripted run${RESET}"
fresh
beat F1 logic logic_f1.txt          last_eval.verdict FAIL
beat F2 chat  chat_f2.txt           phase             LOGIC
beat F3 logic logic_f3.txt          phase             CODE
beat F4 code  code_runtime_error.py last_execution.bucket RUNTIME_ERROR
beat F5 code  code_correct.py       phase             DONE
T1=$(date +%s)

if [ "$BACKUP" = "1" ]; then
  echo
  echo "${BOLD}the Q&A fixtures${RESET}"
  fresh
  beat F3b logic logic_f3b.txt      last_eval.matched_approach sort-two-pointer
  fresh
  beat F6  logic logic_f6.txt       last_eval.verdict          FAIL
  fresh
  post /api/sessions/event "$(body logic logic_f3.txt)" >/dev/null
  beat F4b code  code_tle.py        last_execution.bucket      TLE
fi

# leave the session clean for the human
fresh

echo
echo "${BOLD}timings${RESET}"
for t in "${TIMINGS[@]}"; do
  printf '  %-6s %ss\n' "${t%%:*}" "${t##*:}"
done
echo "  ${DIM}scripted run total: $((T1 - T0))s${RESET}"

echo
if [ "$fail" -eq 0 ]; then
  echo "${GREEN}${BOLD}REHEARSAL GREEN${RESET}  $pass beats passed; session reset and ready"
else
  echo "${RED}${BOLD}REHEARSAL FAILED${RESET}  $fail of $((pass + fail)) beats"
fi
exit "$fail"
