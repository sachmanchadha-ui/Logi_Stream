# CLAUDE.md — LogiStream 3-Day MVP

> **For the human:** put this file at the repo root. Claude Code loads `CLAUDE.md`
> automatically at the start of every session. Drive it day by day:
>
> ```
> Day 1:  "Read CLAUDE.md and PROGRESS.md. Execute Day 1 from D1-T0. Stop at the Day 1 gate."
> Day 2:  "Read CLAUDE.md and PROGRESS.md. Execute Day 2. Stop at the Day 2 gate."
> Day 3:  "Read CLAUDE.md and PROGRESS.md. Execute Day 3."
> Resume: "Read PROGRESS.md and continue from the last incomplete task."
> ```
>
> **Decided Monday night (see §0.1):** Windows + Docker Desktop, `CgroupVersion 2` →
> Judge0 runs as the **hosted API**, not self-hosted. D1-T1 is hosted setup, not a spike.

---

## 0. Who you are and what we are building

You are the principal developer for **LogiStream**, a coding-education platform that makes
students write their algorithm in plain English/Hinglish **before** they may write code.
Wrong logic routes to a Socratic AI tutor that is structurally prevented from giving the answer.

The full design lives in `PROJECT.md` and the case-study report. **This file is the MVP
contract.** Where the two disagree, this file wins; the differences are listed in §3.

**Deadline:** working demo Thursday morning. Build days are Tuesday and Wednesday.
**The only goal:** one reliable happy path, end to end, through all four services, on one problem.

### 0.1 Machine facts (decided — do not re-investigate)

- **Host:** Windows with Docker Desktop. `docker info` reports `CgroupVersion 2`.
- **Judge0:** `JUDGE0_MODE=HOSTED_API` (Judge0 CE via RapidAPI). Self-hosting Judge0 is not
  attempted: its sandbox is incompatible with cgroup v2, and Docker Desktop cannot be switched
  to v1 reliably. The architecture is unchanged — Java owns execution, Python never calls Judge0.
- **Shell:** all scripts in this repo are bash. Run Claude Code and the scripts inside **WSL2
  (Ubuntu)** if available, otherwise Git Bash. Never PowerShell/cmd for repo scripts.
- **Line endings:** add `.gitattributes` with `* text=auto eol=lf` and `*.sh text eol=lf`
  in D1-T0. CRLF in a `.sh` file fails with `$'\r': command not found`.
- **Localhost:** Postgres runs in Docker Desktop and is reachable at `localhost:5432` from WSL2
  and from Windows. If a service in WSL2 cannot reach it, STOP and report rather than rewiring networks.
- **Hosted Judge0 quota is finite.** Every submission AND every poll is a billed request (§8).

---

## 1. Working agreement (read before every task)

1. **One task at a time**, in the order given. Each task ends by running its **Verify** commands.
   A task is done only when Verify passes. Never report success you did not observe.
2. **Log in `PROGRESS.md`** after every task: task id, status, what was built, verify output
   summary, any decision or deviation. This file is how the next session knows where we are.
3. **Commit after every passing task:** `git commit -m "D1-T3: <summary>"`.
4. **STOP and wait for the human** at every **GATE**, and also when:
   - a Verify fails twice after fixes,
   - you are stuck on one issue for more than ~45 minutes,
   - you would need to change a contract in §5 or §6,
   - you would need to add a service, database, or framework not listed here.
   When stopping, give: what failed, what you tried, and 2–3 concrete options.
5. **Never fake the hard parts.** No mocked Judge0 responses, no stubbed LLM verdicts, no
   hardcoded "PASS" to get past a gate. If something doesn't work, stop and say so.
6. **Boring code wins.** Minimal dependencies, no abstractions we don't need this week,
   no premature config systems. Pin dependency versions once they install.
7. **Every service logs the trace id** (`X-Trace-Id`) on every request. Python logs every
   graph node transition with its key outcome. These logs are part of the demo.
8. **Secrets:** read from environment. Never commit `.env`. Commit `.env.example`.

---

## 2. MVP scope

**In scope (must work on stage):**
Next.js UI → Rust gateway → Python/LangGraph evaluates Hinglish logic, tutors Socratically,
verifies every tutor turn → on pass, editor unlocks → code goes Python → Java → Judge0 →
per-test results → failure routes to a code tutor → success.

**Out of scope for the MVP:** CrewAI pipeline, Supabase auth/OAuth, video gating, review queue
UI, transcript archiving, SSE streaming, LiteLLM, Infisical, dashboards, multiple problems,
multiple student languages.

---

## 3. Deviations from the full specification (these go on the demo slide)

| Full spec | MVP | Seam that makes it swappable later |
|---|---|---|
| Supabase JWT validated at edge | Mocked: fixed demo user in Rust | Auth is one extractor in the gateway |
| Supabase Postgres | Local Postgres 16 container | Same SQL, same `DATABASE_URL` |
| Infisical runtime secrets | `.env` file | Everything already reads env vars |
| LiteLLM proxy | Python calls OpenRouter directly (OpenAI-compatible client) | `LLM_BASE_URL` points at LiteLLM later |
| SSE with status heartbeats | Plain HTTP request/response + UI busy state | Response shape unchanged |
| Translation / Syntax / Runtime tutors | One code tutor, failure bucket in its prompt | Bucket mapping still exists; split later |
| Deterministic + LLM-judge verifier | Deterministic verifier (LLM judge = Day 3 stretch) | Judge is an extra check in the same node |
| Multi-language submissions | Python only | `language` is already a request field |
| Spring Data JPA | Spring `JdbcTemplate` (avoids jsonb mapping pain) | Repository layer only |
| Self-hosted Judge0 on an isolated network | Hosted Judge0 CE API (host is cgroup v2) | Only Java's base URL and headers change |
| Offline CrewAI content pipeline | Hand-seeded Two Sum (§7) | Seed format = pipeline output format |
| Review queue / transcripts | FLAGGED verdicts are logged, not queued | Log line marks where the queue goes |
| All services in docker-compose | Infra (Postgres) in compose; services run on host. Containerizing = Day 3 stretch | All URLs are env vars |

---

## 4. Repository layout

```
logistream/
├── CLAUDE.md                 # this file (contract)
├── PROGRESS.md               # task log, decisions, deviations (you maintain it)
├── PROJECT.md                # full design reference
├── .env.example
├── docker-compose.yml        # postgres (and later, optionally, app services)
├── db/
│   ├── init/01_schema.sql
│   ├── init/02_seed.sql      # GENERATED by db/seed/generate_two_sum.py
│   └── seed/generate_two_sum.py
├── judge0/HOSTED.md          # hosted Judge0 CE: endpoint, headers, quota notes
├── scripts/
│   └── judge0_smoke.sh
├── domain/                   # Java 17+, Spring Boot 3, Maven     (port 8080)
├── orchestrator/             # Python 3.11+, FastAPI, LangGraph  (port 8001)
│   ├── app/
│   │   ├── main.py           # FastAPI endpoints
│   │   ├── graph.py          # graph wiring
│   │   ├── state.py
│   │   ├── nodes/            # evaluate_logic, logic_tutor, verify, summarize, execute_code, code_tutor, ...
│   │   ├── verifier.py
│   │   ├── llm.py            # OpenRouter client, JSON parsing + retry
│   │   ├── domain_client.py
│   │   └── prompts/
│   └── scripts/cli_harness.py
├── gateway/                  # Rust, Axum 0.8                    (port 8000)
├── web/                      # Next.js App Router, TS, Tailwind   (port 3000)
└── demo/
    ├── fixtures/             # the scripted submissions (§10)
    ├── start.sh  stop.sh  healthcheck.sh  prewarm.py
    ├── logs/
    └── DEVIATIONS.md
```

### Ports and environment (`.env.example`)

```
# shared
INTERNAL_TOKEN=dev-internal-token-change-me
DATABASE_URL=postgresql://logistream:logistream@localhost:5432/logistream

# orchestrator (Python)
OPENROUTER_API_KEY=
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_EVALUATOR=            # a PAID model slug from openrouter.ai/models; verify it exists
LLM_MODEL_TUTOR=                # may be the same model
FLAG_CONFIDENCE_THRESHOLD=0.6
MAX_REGENERATIONS=2
DOMAIN_URL=http://localhost:8080
ORCHESTRATOR_PORT=8001

# domain (Java)
JUDGE0_URL=https://judge0-ce.p.rapidapi.com     # confirm against the RapidAPI listing
JUDGE0_RAPIDAPI_KEY=                             # from your RapidAPI dashboard
JUDGE0_RAPIDAPI_HOST=judge0-ce.p.rapidapi.com    # confirm against the RapidAPI listing
JUDGE0_PYTHON_LANGUAGE_ID=71                     # verify with GET /languages
JUDGE0_POLL_INTERVAL_MS=1000
JUDGE0_MAX_POLLS=15

# gateway (Rust)
GATEWAY_PORT=8000
ORCHESTRATOR_URL=http://localhost:8001
DOMAIN_URL_FOR_GATEWAY=http://localhost:8080
DEMO_USER_ID=demo-user
CORS_ORIGIN=http://localhost:3000

# web
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000
```

Java and Rust do not read `.env` on their own. Start scripts do `set -a; source .env; set +a`.

---

## 5. Service contracts (do not change without human approval)

### 5.1 Gateway — public API (the ONLY thing the browser talks to)

All responses JSON. Gateway generates `X-Trace-Id` (UUID v4) per request, forwards it
downstream, and returns it in the response header.

| Method | Path | Body | Forwards to |
|---|---|---|---|
| GET | `/health` | – | – |
| GET | `/api/problems/{problem_id}` | – | Java `GET /problems/{problem_id}` |
| POST | `/api/sessions/start` | `{problem_id}` | Python `POST /sessions/{thread_id}/start` |
| POST | `/api/sessions/event` | `{problem_id, type, text}` | Python `POST /sessions/{thread_id}/event` |
| POST | `/api/sessions/reset` | `{problem_id}` | Python `POST /sessions/{thread_id}/reset` |
| GET | `/api/sessions/{problem_id}` | – | Python `GET /sessions/{thread_id}` |

**Identity (mocked auth, real derivation):**
- `user_id = DEMO_USER_ID` (a `X-Demo-User` header may override it, for multi-user testing).
- `thread_id = hex(sha256(user_id + ":" + problem_id))`, computed in Rust.
- **The client never supplies `thread_id`.** Any `thread_id` in a body or header from the browser
  is ignored. This is a real security property of the spec; keep it.

Gateway → Python calls carry `X-Internal-Token: $INTERNAL_TOKEN`, `X-Trace-Id`, `X-User-Id`.
HTTP client timeout: **120 s** (tutor turns can take 20–40 s). CORS: allow `CORS_ORIGIN`.

### 5.2 `SessionView` (returned by every session endpoint, passed through unchanged)

```json
{
  "thread_id": "string",
  "problem_id": "two-sum",
  "phase": "LOGIC | CODE | DONE",
  "status": "LOGIC_WRITE | LOGIC_CHAT | CODE_WRITE | CODE_CHAT | SUCCESS",
  "attempts": { "logic": 0, "code": 0 },
  "accepted_logic": "string | null",
  "messages": [
    { "role": "student | tutor | system", "kind": "logic | chat | code | hint | result | info",
      "text": "string", "ts": "ISO-8601" }
  ],
  "last_eval": {
    "verdict": "PASS | FAIL | FLAGGED",
    "matched_approach": "string | null",
    "missing_steps": ["string"],
    "violated_invariants": ["string"],
    "misconception_id": "string | null",
    "confidence": 0.0,
    "cache_hit": false
  },
  "last_execution": {
    "bucket": "ACCEPTED | WRONG_ANSWER | TLE | COMPILE_ERROR | RUNTIME_ERROR | INFRA_ERROR",
    "passed": 0, "total": 5,
    "tests": [
      { "index": 1, "label": "string", "is_public": true, "passed": true,
        "status": "string", "time": "0.02",
        "stdin": "only if is_public", "expected": "only if is_public",
        "stdout": "only if is_public", "stderr_excerpt": "string" }
    ]
  },
  "debug": {
    "trace_id": "string",
    "last_node_path": ["await_input", "evaluate_logic", "logic_tutor", "verify_logic"],
    "regenerations": 0,
    "verifier_rejections": [ { "reason": "string" } ],
    "fallback_used": false
  }
}
```

`last_eval` and `last_execution` are `null` until they exist. The evaluator's free-text
`rationale` is logged server-side and **never** returned.

### 5.3 Orchestrator (Python) — internal API

Every endpoint except `/health` requires `X-Internal-Token`; reject with 401 otherwise.

| Method | Path | Body | Behaviour |
|---|---|---|---|
| GET | `/health` | – | `{ok:true}` |
| POST | `/sessions/{thread_id}/start` | `{problem_id, user_id}` | If a checkpoint exists, return its view (resume). Else start graph → it stops at `await_input`. Return view. |
| POST | `/sessions/{thread_id}/event` | `{type, text}` | `graph.invoke(Command(resume={type,text}), config)`. Return view. |
| POST | `/sessions/{thread_id}/reset` | – | Delete the thread's checkpoints. `{ok:true}` |
| GET | `/sessions/{thread_id}` | – | Return view from `graph.get_state(config)` |

Event validation (return **409** with a readable message if violated):
`logic` only in phase LOGIC · `code` only in phase CODE · `chat` in LOGIC or CODE · nothing in DONE.
Empty/whitespace `text` → 422.

Build the view from `graph.get_state(config).values`. Do not rely on the return shape of `invoke`.

### 5.4 Domain (Java) — API

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/health` | – | `{ok:true}` |
| GET | `/problems/{id}` | – | `{id, title, description, examples:[{input, output, explanation}], starter_code, language:"python"}` — **no rubric, no hidden tests** |
| GET | `/internal/problems/{id}/context` | token | `{id, title, description, rubric, rubric_version, starter_code}` |
| POST | `/internal/execute` | token | see below |

`POST /internal/execute` request: `{problem_id, language:"python", source}`

Response:
```json
{
  "bucket": "ACCEPTED | WRONG_ANSWER | TLE | COMPILE_ERROR | RUNTIME_ERROR | INFRA_ERROR",
  "passed": 3, "total": 5, "infra_retry_used": false,
  "tests": [
    { "index": 1, "label": "basic", "is_public": true, "status_id": 3,
      "status_description": "Accepted", "passed": true, "time": "0.02",
      "stdin": "...", "expected": "...", "stdout": "...", "stderr": "..." }
  ]
}
```
Java returns full detail (including hidden stdin/expected) **to Python only**. Python strips
hidden-test inputs/expected/stdout before anything reaches `SessionView`.

---

## 6. Orchestrator design (LangGraph)

### 6.1 The session is one long-running graph; every student action is a resume

```
START → await_input ──(logic)──► evaluate_logic ──PASS/FLAGGED──► summarize_logic ─► await_input
            │                          └──FAIL──► logic_tutor ⇄ verify_logic ─────────► await_input
            ├──(chat, LOGIC)──► logic_tutor ⇄ verify_logic ─────────────────────────► await_input
            ├──(code)──► execute_code ──ACCEPTED──► finish ─► END
            │                 ├──INFRA_ERROR──(system message, no tutor)────────────► await_input
            │                 └──other──► code_tutor ⇄ verify_code ─────────────────► await_input
            └──(chat, CODE)──► code_tutor ⇄ verify_code ───────────────────────────► await_input
```

- **`await_input` contains ONLY `event = interrupt({...})`** and writes the event plus the student
  message into state. **Critical:** on resume, LangGraph re-executes the interrupted node from
  its first line. Any LLM call or side effect placed before `interrupt()` would run twice.
- Routing out of `await_input` is a conditional edge on `(event.type, phase)`.
- `⇄` = verify loop: verifier rejects → `regenerations += 1` → regenerate, up to
  `MAX_REGENERATIONS`; then use the canned fallback (§6.4) and set `fallback_used`. Reset
  `regenerations` to 0 after each delivered tutor turn.

### 6.2 State (`TypedDict`, plain JSON-serializable types only)

```
problem_id, user_id, thread_id
phase: "LOGIC"|"CODE"|"DONE"
status: "LOGIC_WRITE"|"LOGIC_CHAT"|"CODE_WRITE"|"CODE_CHAT"|"SUCCESS"
pending_event: {type, text} | None
user_logic, user_code: str
accepted_logic: str | None
logic_summary: dict | None
last_eval: dict | None
last_execution: dict | None          # full Java detail (Python-side only)
attempts: {"logic": int, "code": int}
draft: str | None                    # tutor draft awaiting verification
regenerations: int
verifier_rejections: list[dict]
fallback_used: bool
node_path: list[str]                 # reset at each await_input
messages: Annotated[list[dict], operator.add]
```

Keep the problem context (description, rubric) out of state; fetch it from Java via
`domain_client` and cache it in-process per `problem_id`.

### 6.3 Nodes

**`evaluate_logic`** — `attempts.logic += 1`.
- Cache key: `sha256(problem_id + ":" + rubric_version + ":" + normalize(text))`,
  normalize = lowercase, strip, collapse whitespace. Table `orch.verdict_cache`. On hit, skip
  the LLM, set `cache_hit: true`.
- LLM call: `temperature=0`, JSON only. Input = problem description + rubric + student text.
  Must accept English, Hindi-in-Latin-script, and mixed Hinglish equally.
- Model output schema: `{verdict: "PASS"|"FAIL", matched_approach, missing_steps[],
  violated_invariants[], misconception_id, confidence, rationale}`.
- **FLAGGED is computed in code, not by the model:** if `matched_approach is None` and
  `violated_invariants == []` and `confidence < FLAG_CONFIDENCE_THRESHOLD` → `FLAGGED`
  (treated as pass). Log `FLAGGED — would enter review queue (cut for MVP)`.
- Parse with pydantic; on parse failure retry once with "return valid JSON only"; on second
  failure raise a clear error (do NOT default to PASS or FAIL).

**`logic_tutor`** — Socratic. Input: `last_eval` fields, the misconception's `socratic_counter`
as inspiration, last ~10 messages. Rules in the prompt: one guiding question per turn, ≤ 80 words,
reply in the student's register (Hinglish if they wrote Hinglish), never name the approach or data
structure, never give steps in order, never write code. If chat arrives before any logic submission,
ask them to submit their logic first. Writes `draft`.

**`verify_logic` / `verify_code`** — see §6.4.

**`summarize_logic`** — one LLM call → `{approach_taken, key_steps[], misconceptions_corrected[],
final_logic_text}`. On any failure, fall back to `{final_logic_text: user_logic}`. Sets
`accepted_logic`, `phase=CODE`, `status=CODE_WRITE`, appends a system message.

**`execute_code`** — calls Java `/internal/execute`. `attempts.code += 1` unless the bucket is
`INFRA_ERROR`. `ACCEPTED` → `finish`. `INFRA_ERROR` → system message "The sandbox failed; this
attempt does not count" → `await_input`. Otherwise → `code_tutor`.

**`code_tutor`** — input: bucket, per-test results (hidden tests: only label + status), stderr,
student code, `logic_summary`. Explains the failure in terms of the student's own accepted logic.
May quote a short piece of the student's own code and name the broken construct. Must not write
the solution or the full corrected function.

**`finish`** — `phase=DONE`, `status=SUCCESS`, success message → END.

### 6.4 Verifier (deterministic, `verifier.py`, fully unit-tested)

Logic phase — reject the draft if any:
- contains a code fence (```` ``` ````),
- matches code-like lines: `^\s*(def|for|while|if|elif|return|import|class)\b.*:\s*$` or
  `\w+\s*=\s*(\{\}|\[\]|dict\(|set\()` or `in range\(` or `\.get\(`,
- contains any rubric `forbidden_terms_logic_tutor` (case-insensitive, word-boundary match),
- is longer than 120 words.

Code phase — reject the draft if any:
- contains `def two_sum` (or `def <entrypoint>` from the rubric),
- contains a code block longer than 3 lines,
- is longer than 160 words.

Each rejection appends `{reason}` to `verifier_rejections`. After `MAX_REGENERATIONS`, deliver the
fallback: logic phase → the rubric's `socratic_counter` for `misconception_id` (or a generic
"Walk me through what happens on a small example, step by step."); code phase → a generic
"Run your function by hand on the first failing public example and compare each step with your
logic." Unverified text is **never** delivered.

### 6.5 Persistence

- Day 1: `MemorySaver`. Day 2: `PostgresSaver` (`langgraph-checkpoint-postgres`, psycopg 3).
- Use a `psycopg_pool.ConnectionPool` with `kwargs={"autocommit": True, "prepare_threshold": 0,
  "row_factory": dict_row}`; call `checkpointer.setup()` once at startup.
- Reset: `checkpointer.delete_thread(thread_id)` if available in the installed version; otherwise
  delete that thread's rows from the checkpoint tables. Check the installed version's docs.
- Use sync FastAPI endpoints (`def`, not `async def`) with the sync graph. Simpler; fine for a demo.

---

## 7. Data: schema and seed

### 7.1 Schema (`db/init/01_schema.sql`)

```sql
CREATE SCHEMA IF NOT EXISTS app;   -- owned by Java
CREATE SCHEMA IF NOT EXISTS orch;  -- owned by Python (LangGraph tables go in public via setup())

CREATE TABLE app.users (id TEXT PRIMARY KEY, display_name TEXT NOT NULL);

CREATE TABLE app.problems (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,          -- markdown
  examples JSONB NOT NULL,
  starter_code TEXT NOT NULL,
  harness_python TEXT NOT NULL,       -- appended after student code by Java
  rubric JSONB NOT NULL,
  rubric_version INT NOT NULL DEFAULT 1,
  cpu_time_limit NUMERIC NOT NULL DEFAULT 2,
  wall_time_limit NUMERIC NOT NULL DEFAULT 5,
  memory_limit_kb INT NOT NULL DEFAULT 128000
);

CREATE TABLE app.hidden_tests (
  problem_id TEXT REFERENCES app.problems(id),
  idx INT NOT NULL,
  label TEXT NOT NULL,
  is_public BOOLEAN NOT NULL DEFAULT FALSE,
  stdin TEXT NOT NULL,
  expected_output TEXT NOT NULL,
  PRIMARY KEY (problem_id, idx)
);

CREATE TABLE orch.verdict_cache (
  cache_key TEXT PRIMARY KEY,
  problem_id TEXT NOT NULL,
  verdict JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.2 Seed: Two Sum (`db/seed/generate_two_sum.py` writes `db/init/02_seed.sql`)

**Description (markdown):** Given an array of integers `nums` and an integer `target`, return the
indices of the two numbers that add up to `target`. Exactly one valid answer exists. You may not
use the same element twice. Return the indices in any order. Constraints: `2 ≤ n ≤ 20,000`;
your solution must be faster than checking every pair.

**Starter code:**
```python
def two_sum(nums, target):
    pass
```

**Harness (appended by Java after the student's code):**
```python
import sys as _sys, json as _json
_data = _json.loads(_sys.stdin.read())
print(_json.dumps(sorted(list(two_sum(_data["nums"], _data["target"])))))
```

**Tests** (stdin is `{"nums": [...], "target": N}`; expected is exactly `json.dumps(sorted(indices))`):

| idx | label | public | nums / target | expected |
|---|---|---|---|---|
| 1 | basic | yes | `[2,7,11,15]`, 9 | `[0, 1]` |
| 2 | middle pair | yes | `[3,2,4]`, 6 | `[1, 2]` |
| 3 | duplicates | no | `[3,3]`, 6 | `[0, 1]` |
| 4 | negatives | no | `[-3,4,3,90]`, 0 | `[0, 2]` |
| 5 | large input (n=20,000) | no | generated, deterministic seed, unique answer at the last two positions | computed by the script |

Test 5 must make a nested-loop Python solution exceed `cpu_time_limit=2` while a single-pass
solution finishes well under it. The generator must **assert** the answer is unique.

**Rubric JSON** (store exactly this in `app.problems.rubric`):
```json
{
  "problem_id": "two-sum",
  "rubric_version": 1,
  "entrypoint": "two_sum",
  "approaches": [
    { "id": "lookup-single-pass",
      "label": "Single pass with a lookup of previously seen values",
      "steps": ["go through the array once",
                "for each element, compute the value still needed to reach the target",
                "check whether that needed value was already seen",
                "if seen, return its stored index together with the current index",
                "otherwise remember the current value with its index"],
      "complexity": "O(n) time" },
    { "id": "sort-two-pointer",
      "label": "Sort value-index pairs, then move two pointers inward",
      "steps": ["pair each value with its original index",
                "sort the pairs by value",
                "start one pointer at each end",
                "if the sum is too small move the left pointer right; if too large move the right pointer left",
                "when the sum equals the target return the two ORIGINAL indices"],
      "complexity": "O(n log n) time" }
  ],
  "invariants": [
    "returns indices, not values",
    "never uses the same element twice",
    "is faster than checking every pair (better than O(n^2))",
    "describes when the search stops"
  ],
  "misconceptions": [
    { "id": "nested-loop", "pattern": "checks every pair with two nested loops",
      "socratic_counter": "Agar array mein 20,000 numbers hon, toh tumhara approach kitne pairs check karega? Kya har pair ko dekhna sach mein zaroori hai?" },
    { "id": "returns-values", "pattern": "returns the numbers instead of their positions",
      "socratic_counter": "Question dhyan se padho — woh numbers maang raha hai, ya unki positions?" },
    { "id": "same-element-twice", "pattern": "may pair an element with itself",
      "socratic_counter": "Agar target 6 hai aur array mein sirf ek 3 hai, kya tumhara logic galti se 3 + 3 bana dega?" },
    { "id": "sort-loses-indices", "pattern": "sorts and then returns indices from the sorted array",
      "socratic_counter": "Sort karne ke baad, kya har number ki position wahi rehti hai jo original array mein thi?" }
  ],
  "forbidden_terms_logic_tutor": ["hashmap", "hash map", "hash table", "dictionary", "dict",
                                   "complement", "two pointer", "two pointers", "two-pointer"]
}
```

Also seed `app.users`: `('demo-user', 'Demo Student')`.

---

## 8. Judge0 integration rules (Java)

- Use `base64_encoded=true` in both directions (avoids UTF-8 failures); decode in Java.
- Submit all tests in one `POST /submissions/batch`, then poll `GET /submissions/batch?tokens=…`
  every `JUDGE0_POLL_INTERVAL_MS` (1 s) for at most `JUDGE0_MAX_POLLS` (15). Anything still in
  status 1/2 after that → `INFRA_ERROR`. Request only the fields you use (`fields=` parameter).
- **Quota discipline (hosted API):** one code run costs 1 batch submit + every poll. Log a running
  request counter per run. Never add automatic retries beyond the single infra retry in the table
  below. Verify scripts must print how many Judge0 requests they consumed.
- **Do not send `expected_output` to Judge0.** Java compares `stdout.strip()` to
  `expected_output.strip()` itself. Status 3 + mismatch → test is Wrong Answer. This avoids
  Judge0 whitespace-comparison surprises.
- Per submission: `language_id=JUDGE0_PYTHON_LANGUAGE_ID`, `cpu_time_limit`, `wall_time_limit`,
  `memory_limit` from the problem row. Source = student code + `"\n\n"` + harness.
- If `JUDGE0_RAPIDAPI_KEY` is set, add `X-RapidAPI-Key` and `X-RapidAPI-Host` headers (hosted fallback).

**Bucket mapping** (worst wins, in this priority):

| Condition | Bucket |
|---|---|
| any status 13 or 14 (after one full retry of the batch) | `INFRA_ERROR` |
| **Python-specific:** status 11/NZEC whose stderr contains `SyntaxError` or `IndentationError` | `COMPILE_ERROR` |
| any status 6 | `COMPILE_ERROR` |
| any status 7–12 | `RUNTIME_ERROR` |
| any status 5 | `TLE` |
| any status 4, or status 3 with stdout mismatch | `WRONG_ANSWER` |
| all status 3 and all stdout match | `ACCEPTED` |

The Python rule matters: Judge0 has no compile step for Python, so syntax errors arrive as runtime
errors. Without reclassification the "syntax" path never fires.

---

## 9. Day plan

### DAY 1 — Tuesday: prove the two hard integrations in isolation

**D1-T0 · Toolchain and skeleton (~20 min)**
Confirm you are running in WSL2 or Git Bash (§0.1). Check versions: docker, node ≥ 20, cargo,
java ≥ 17, mvn, python ≥ 3.11. `git init`, create §4 layout, `.gitignore`, `.gitattributes`
(LF endings, §0.1), `.env.example`, `PROGRESS.md` with a task table.
*Verify:* all version commands succeed; tree matches §4; `git check-attr eol -- scripts/x.sh`
reports `lf`. If a tool is missing, STOP and list it with the install command for this shell.

**D1-T1 · Hosted Judge0 setup (~30 min; decided in §0.1, no spike)**
The human provides `JUDGE0_RAPIDAPI_KEY` in `.env` (subscribed to Judge0 CE on RapidAPI).
Write `judge0/HOSTED.md` (mode, endpoint, headers, quota notes) and `scripts/judge0_smoke.sh`:
fetch `/languages` once and confirm the Python 3 id, submit `print("hello")` via the batch
endpoint, poll per §8, assert status 3 and stdout `hello`. Print the number of Judge0 requests used.
*Verify:* smoke script passes; request count printed.
Record in PROGRESS.md: `JUDGE0_MODE=HOSTED_API`, confirmed language id, and the plan's daily
request limit as shown on the RapidAPI dashboard. If the key is missing or the call returns 401/403,
STOP and ask the human.

**D1-T2 · Postgres, schema, seed (~45 min)**
`docker-compose.yml` with `postgres:16` (db/user/password `logistream`, port 5432, named volume,
`db/init` mounted to `/docker-entrypoint-initdb.d`). Write the generator from §7.2 and generate `02_seed.sql`.
*Verify:* `docker compose up -d postgres`; psql shows 1 problem, 5 tests, rubric JSON valid,
test 5 answer unique (generator assertion ran).

**D1-T3 · Java domain service (~3 h)**
Spring Boot 3 (Maven; web, jdbc, postgresql, actuator optional). `JdbcTemplate`. Endpoints §5.4.
Internal-token filter on `/internal/**` (401 without it). Judge0 client per §8 with config from env.
*Verify* (write `domain/verify.sh` so it can be re-run):
- `GET /problems/two-sum` → no `rubric`, no hidden tests.
- `/internal/execute` without token → 401.
- correct single-pass solution → `ACCEPTED`, 5/5.
- nested-loop solution → `TLE` (test 5).
- missing colon → `COMPILE_ERROR` (via the Python SyntaxError rule).
- `seen[target - x]` without a membership check → `RUNTIME_ERROR`.
- returns values instead of indices → `WRONG_ANSWER`.

**D1-T4 · Python orchestrator core, no HTTP (~3 h)**
venv + deps (fastapi, uvicorn, langgraph, langgraph-checkpoint-postgres, psycopg[binary,pool],
openai, httpx, pydantic). `llm.py` (OpenAI client with `base_url=LLM_BASE_URL`), `domain_client.py`,
`state.py`, `verifier.py` + unit tests, nodes for the LOGIC phase (`await_input`, `evaluate_logic`,
`logic_tutor`, `verify_logic`, `summarize_logic`), graph with `MemorySaver`.
`scripts/cli_harness.py`: interactive loop — type `logic: …` / `chat: …`, prints each node path,
verdict fields, and the delivered tutor message.
*Verify:*
- `pytest` for the verifier passes (include a draft containing "hashmap", one with a code fence,
  one clean Socratic question).
- Fixture F1 (§10) → `FAIL`, `misconception_id=nested-loop`, delivered hint contains no forbidden term.
- Fixture F2 as chat → a tutor reply, graph back at `await_input`.
- Fixture F3 → `PASS`, `matched_approach=lookup-single-pass`, phase becomes CODE.
- Fixture F3 again in a fresh thread → `cache_hit: true`, no LLM call in the log.
- Fixture F3b (sort + two pointer) → `PASS`, `matched_approach=sort-two-pointer`.
- Fixture F6 (gaming: "use hashmap") → `FAIL`.
Print all fixture verdicts as a table in PROGRESS.md (this is the mini golden set).

**🚦 DAY 1 GATE — STOP.** Report: Judge0 mode, Java verify results, fixture verdict table, and
anything that looks fragile. Wait for the human.

### DAY 2 — Wednesday: wire it end to end

**D2-T1 · Code phase in the graph (~2 h)**
Nodes `execute_code`, `code_tutor`, `verify_code`, `finish`; hidden-test stripping (§5.4).
Extend the CLI harness with `code: <path-to-file>`.
*Verify:* full CLI run F1 → F2 → F3 → F4 (runtime error → code tutor turn, no full solution in it)
→ F5 (ACCEPTED → DONE). Also run the nested-loop code fixture → `TLE` → tutor talks about scale.

**D2-T2 · PostgresSaver + FastAPI (~1.5 h)**
Swap to `PostgresSaver` (§6.5). Endpoints §5.3, token check, 409/422 validation, view builder,
per-node logging with trace id.
*Verify* (`orchestrator/verify_api.sh`): start → logic F1 → chat F2 → **kill and restart uvicorn**
→ `GET` shows the conversation intact → logic F3 → phase CODE → reset → fresh state.
Wrong event type for the phase → 409. No token → 401.

**D2-T3 · Rust gateway (~1.5 h)**
Axum **0.8** (path params are `/{id}`; the old `/:id` syntax panics at startup), tokio, reqwest
(explicit 120 s timeout), tower-http (CORS, trace), sha2, hex, uuid, tracing. Routes §5.1, mocked
auth, thread derivation, trace id generation and propagation, upstream errors passed through with
their status code.
*Verify* (`gateway/verify.sh`): full flow via port 8000 only; a body containing
`"thread_id": "attacker"` and a header `X-Thread-Id: attacker` are both ignored (same thread as
without them); `X-Demo-User: other` gets a different, empty session; `X-Trace-Id` appears in
gateway, Python, and Java logs for the same request.

**D2-T4 · Next.js UI (~3 h)**
Single page, dark mode, App Router, Tailwind. Talks only to the gateway.
- Header: "LogiStream", phase stepper (Logic → Code → Done), attempt counts, **Reset** button.
- Left pane: problem + examples. In CODE phase, tabs: *Problem* | *Your accepted logic*.
- Right pane: LOGIC → textarea + "Submit logic". CODE → Monaco (Python, dark) + "Run & submit".
  Monaco must be client-only: `dynamic(() => import(...), { ssr: false })`.
- Floating chat panel over the right pane (opens automatically on a tutor message) with an input
  that sends `chat` events.
- Bottom drawer (CODE phase): per-test rows; public tests show input/expected/output, hidden tests
  show only label + pass/fail + status.
- **"Under the hood" collapsible panel:** `last_eval` (verdict, approach, missing steps,
  misconception, confidence, cache hit), verifier rejections, regenerations, fallback flag,
  bucket, node path, trace id. This panel is how examiners *see* the architecture. It is core, not stretch.
- Busy states with a live seconds counter: "Evaluating your logic…", "Tutor is thinking…",
  "Running tests in the sandbox…". Disable inputs while busy.
- On page load, call `start` and render (a refresh must resume the session, visibly).
*Verify:* the human runs the §10 script in the browser. You provide the exact click-by-click steps.

**🚦 DAY 2 GATE — STOP.** Three full browser runs of §10 without restarting any service. Report
timings per step and any flaky behaviour.

### DAY 3 — Wednesday night → Thursday morning: harden and rehearse

**D3-T1 · Stretch (only if the Day 2 gate passed cleanly; stop at 8 pm regardless)**, in order:
1. LLM judge in `verify_logic` (logic phase only; prompt includes the rubric and what must not be
   revealed; runs only if the deterministic check passed).
2. Containerize app services under a compose profile `full` (URLs via env; same `.env`).
3. SSE status heartbeats. Only if 1 and 2 are done and stable. Probably skip.

**🧊 8 PM FEATURE FREEZE.** After this: bug fixes only.

**D3-T2 · Demo tooling**
`demo/start.sh` (source `.env`, start postgres, then Java, Python, Rust, Next; logs to
`demo/logs/*.log`; waits on `/health` of each), `demo/stop.sh`, `demo/healthcheck.sh` (all
`/health` + ONE Judge0 smoke submission — it costs quota, so it is opt-in via `--judge0`),
`demo/DEVIATIONS.md` (§3 table plus "Judge0: hosted API instead of self-hosted", slide-ready).

**D3-T3 · Cold start test**
`demo/stop.sh`, `docker compose down -v`, `demo/start.sh`, full §10 run.
*Verify:* green from zero, total boot time recorded.

**D3-T4 · Pre-warm (AFTER the cold start test — `down -v` wipes the verdict cache)**
`demo/prewarm.py` runs every logic fixture through the gateway, then resets the session.
*Verify:* re-running the logic fixtures shows `cache_hit: true`.
**From here on, never run `docker compose down -v`.** Thursday uses `demo/start.sh` only.

**D3-T5 · Rehearsal support**
Help the human rehearse §10 three times; fix only real bugs. Remind the human to record a
backup screen video of a clean run.

**Thursday morning checklist (for the human):** start 30 min early → `demo/start.sh` →
`demo/healthcheck.sh` → one quick run → Reset → present.

---

## 10. Demo script and fixtures (`demo/fixtures/`)

| Id | Step | Input | Expected |
|---|---|---|---|
| F1 | submit logic | "Main har number ke liye baaki saare numbers check karunga, do loops laga ke. Jab dono ka sum target ke barabar ho jaye toh unke index return kar dunga." | FAIL, `nested-loop`, Socratic question about scale, no forbidden terms |
| F2 | chat | "20,000 numbers pe toh lagbhag 20 crore pairs ho jayenge. Kya main pehle dekhe hue numbers kahin yaad rakh sakta hoon?" | Tutor encourages/probes, still no forbidden terms |
| F3 | submit logic | "Main array ko ek hi baar traverse karunga. Har number ke liye dekhunga ki target minus current number pehle aa chuka hai ya nahi — uske liye ek lookup rakhunga jismein value se uska index mil jaye. Agar mil gaya toh dono indices return kar dunga, warna current number aur uska index lookup mein daal dunga. Check pehle hota hai aur insert baad mein, isliye same element do baar use nahi hoga." | PASS, `lookup-single-pass`, editor unlocks |
| F3b | submit logic (Q&A backup) | "Main har number ke saath uska original index jod ke list ko value ke hisaab se sort karunga. Phir ek pointer shuru mein aur ek end mein. Sum chhota ho toh left aage, bada ho toh right peeche. Jab sum target ke barabar ho, dono ke original index return kar dunga." | PASS, `sort-two-pointer` (shows valid alternatives are accepted) |
| F4 | submit code | runtime-error code below | RUNTIME_ERROR → code tutor, no full solution |
| F4b | submit code (optional) | nested-loop code | TLE on "large input" → tutor on scale |
| F5 | submit code | correct code below | ACCEPTED 5/5 → SUCCESS |
| F6 | gaming (Q&A backup) | "use hashmap" | FAIL |

F4 (runtime error):
```python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        j = seen[target - x]
        return [j, i]
```

F4b (TLE):
```python
def two_sum(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
```

F5 (correct):
```python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
```

**Stage narrative:** F1 (the tutor refuses to hand over the answer) → open "Under the hood"
(structured diagnosis, misconception id) → F2 (conversation continues) → refresh the page
(session survives: checkpointing) → F3 (unlock) → F4 (sandbox catches a runtime error, tutor
explains without solving) → F5 (success). Keep F3b, F4b, F6 for questions.

---

## 11. Known traps (check here before debugging)

1. **Judge0 quota (hosted)**: each submit and each poll is a request. A tight poll loop or an
   auto-retry can exhaust the daily limit before the demo. Watch the request counter.
2. **Python syntax errors from Judge0 arrive as Runtime Error (NZEC)**, not Compilation Error. §8 rule.
3. **LangGraph re-runs the interrupted node from its first line on resume.** `await_input` must
   contain nothing but `interrupt()` and state writes that are safe to repeat.
4. **PostgresSaver** needs `autocommit=True`, `prepare_threshold=0`, `dict_row`, and `setup()` once.
5. **Axum 0.8** path syntax is `/{param}`.
6. **CORS**: gateway must allow `http://localhost:3000`, including the preflight for JSON POSTs.
7. **Monaco in Next.js** must be dynamically imported with `ssr: false`.
8. **Timeouts**: reqwest has no overall timeout unless you set one; set 120 s. The browser must not
   abort long requests either.
9. **Judge0 text encoding**: always `base64_encoded=true`.
10. **`docker compose down -v`** deletes the verdict cache and checkpoints. Not after D3-T4.
11. **Model JSON drift**: always parse with pydantic and retry once; never silently default a verdict.
12. **OpenRouter model slugs change**: verify `LLM_MODEL_*` exists before Day 1 T4. Use a paid
    model; a rate limit on stage is unrecoverable.

---

## 12. Risk #1 (resolved Monday night) and the risk that replaced it

**Original risk:** Judge0's sandbox is incompatible with cgroup v2. The demo machine is Windows +
Docker Desktop reporting `CgroupVersion 2`, so self-hosting was ruled out before Day 1 and the
hosted API was chosen (§0.1). No time is spent on the spike.

**New Risk #1: the hosted API on stage.** Two failure modes:
- **Quota exhaustion.** Development, verify scripts, rehearsals, and pre-warming all consume
  requests. If the free plan's daily limit is small, the human should subscribe to the cheapest
  paid tier for Wednesday–Thursday. Verify scripts report their request usage so the burn rate
  is visible (§8).
- **Network on stage.** The demo depends on the internet for both OpenRouter and Judge0. The
  backup screen recording (D3-T5) covers this; the human should also have a phone hotspot ready.

Runner-up risk: LangGraph interrupt/resume bugs. Mitigated by building on `MemorySaver` with the CLI
harness first (Day 1), so state bugs are separated from HTTP bugs before `PostgresSaver` goes in.
