#!/usr/bin/env bash
# D1-T2 verify: schema + seed loaded correctly (CLAUDE.md section 7).
# Re-runnable. Uses psql inside the container, so no local psql client needed.
set -uo pipefail

PSQL="docker compose exec -T postgres psql -U logistream -d logistream -At"
fails=0

check() {  # check <label> <expected> <sql>
  local label="$1" expected="$2" sql="$3" actual
  actual=$($PSQL -c "$sql" 2>&1 | tr -d '\r' | tr -d '\n')
  if [ "$actual" = "$expected" ]; then
    printf '  PASS  %-46s %s\n' "$label" "$actual"
  else
    printf '  FAIL  %-46s expected=%s actual=%s\n' "$label" "$expected" "$actual"
    fails=$((fails + 1))
  fi
}

echo "=== D1-T2 verify: schema and seed ==="

check "schemas app+orch exist" "2" \
  "SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('app','orch');"

check "tables created" "4" \
  "SELECT count(*) FROM information_schema.tables
   WHERE (table_schema='app' AND table_name IN ('users','problems','hidden_tests'))
      OR (table_schema='orch' AND table_name='verdict_cache');"

check "one problem seeded" "1" "SELECT count(*) FROM app.problems;"
check "problem id" "two-sum" "SELECT id FROM app.problems;"
check "demo user seeded" "1" "SELECT count(*) FROM app.users WHERE id='demo-user';"
check "five tests seeded" "5" "SELECT count(*) FROM app.hidden_tests WHERE problem_id='two-sum';"
check "two public tests" "2" \
  "SELECT count(*) FROM app.hidden_tests WHERE problem_id='two-sum' AND is_public;"

# rubric integrity: it is jsonb, so a bad value could not have been inserted at all.
# These assert the shape the orchestrator and verifier actually depend on.
check "rubric version" "1" "SELECT rubric_version FROM app.problems WHERE id='two-sum';"
check "rubric entrypoint" "two_sum" \
  "SELECT rubric->>'entrypoint' FROM app.problems WHERE id='two-sum';"
check "rubric approaches" "lookup-single-pass,sort-two-pointer" \
  "SELECT string_agg(a->>'id', ',' ORDER BY ord)
   FROM app.problems, jsonb_array_elements(rubric->'approaches') WITH ORDINALITY t(a, ord)
   WHERE id='two-sum';"
check "rubric misconceptions" "4" \
  "SELECT jsonb_array_length(rubric->'misconceptions') FROM app.problems WHERE id='two-sum';"
check "rubric invariants" "4" \
  "SELECT jsonb_array_length(rubric->'invariants') FROM app.problems WHERE id='two-sum';"
check "forbidden terms" "9" \
  "SELECT jsonb_array_length(rubric->'forbidden_terms_logic_tutor')
   FROM app.problems WHERE id='two-sum';"
check "every misconception has a counter" "4" \
  "SELECT count(*) FROM app.problems, jsonb_array_elements(rubric->'misconceptions') m
   WHERE id='two-sum' AND length(m->>'socratic_counter') > 20;"
check "examples seeded" "2" \
  "SELECT jsonb_array_length(examples) FROM app.problems WHERE id='two-sum';"

check "limits (cpu/wall/mem)" "2|5|128000" \
  "SELECT cpu_time_limit || '|' || wall_time_limit || '|' || memory_limit_kb
   FROM app.problems WHERE id='two-sum';"

check "harness calls the entrypoint" "t" \
  "SELECT harness_python LIKE '%two_sum(_data[\"nums\"], _data[\"target\"])%'
   FROM app.problems WHERE id='two-sum';"

# test 5 is the TLE test: it must really be 20,000 elements and the answer must
# sit at the last two positions, or a nested loop would exit early and pass.
check "test 5 has n=20000" "20000" \
  "SELECT jsonb_array_length((stdin::jsonb)->'nums')
   FROM app.hidden_tests WHERE problem_id='two-sum' AND idx=5;"
check "test 5 answer at last two positions" "[19998, 19999]" \
  "SELECT expected_output FROM app.hidden_tests WHERE problem_id='two-sum' AND idx=5;"
check "test 5 pair really sums to target" "t" \
  "SELECT ((stdin::jsonb)->'nums'->>19998)::bigint + ((stdin::jsonb)->'nums'->>19999)::bigint
          = ((stdin::jsonb)->>'target')::bigint
   FROM app.hidden_tests WHERE problem_id='two-sum' AND idx=5;"

# uniqueness of the answer, re-derived in SQL rather than trusting the generator
check "test 5 answer is unique" "1" \
  "WITH t AS (SELECT stdin::jsonb j FROM app.hidden_tests
              WHERE problem_id='two-sum' AND idx=5),
        n AS (SELECT (v)::bigint val, (ord-1) idx
              FROM t, jsonb_array_elements_text(j->'nums') WITH ORDINALITY x(v, ord)),
        tg AS (SELECT (j->>'target')::bigint g FROM t)
   SELECT count(*) FROM n a JOIN n b ON a.idx < b.idx, tg
   WHERE a.val + b.val = tg.g;"

echo
if [ "$fails" -eq 0 ]; then
  echo "D1-T2 VERIFY: all checks passed"
else
  echo "D1-T2 VERIFY: $fails check(s) FAILED"
fi
exit "$fails"
