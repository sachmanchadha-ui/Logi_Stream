# PROGRESS — LogiStream 3-Day MVP

Task log, decisions and deviations. Updated after every task (see CLAUDE.md §1).

## Environment facts (established D1-T0, 2026-09-21)

| Fact | Value |
|---|---|
| Repo root | `G:\fsjp_project_completed` |
| Shell | **Git Bash (MINGW64)** — WSL2 has no Ubuntu distro, only the internal `docker-desktop` one (§0.1 fallback) |
| Docker | 29.8.0, Compose v5.5.1, daemon up, `CgroupVersion 2` |
| Node | v26.5.0 (npm 11.17.0) — OK (≥ 20) |
| Python (PATH) | 3.14.7 — used by the Java sandbox to run student code |
| Python (uv) | **3.11.15** via `uv` 0.11.32 — the orchestrator venv |
| Java | **Temurin 21.0.12.1 LTS** in `tools/jdk21`, pinned via `scripts/env.sh`. Machine default (26.0.2) untouched |
| Maven | **3.9.16** in `tools/maven` |
| Rust / cargo | **1.98.1** (rustup, per-user `~/.cargo`) |
| MSVC linker | present (Visual Studio 18) — `cargo` can link on this box |
| Package managers | `winget` 1.29.290, `choco` 2.7.3, `uv` 0.11.32 |
| `jq` | **not installed** — shell scripts parse JSON with `python` |

## Task log

| Task | Status | Notes |
|---|---|---|
| D1-T0 Toolchain and skeleton | ✅ DONE | Layout per §4, `.gitattributes` (LF), `.gitignore`, `.env.example`, `git init`. Toolchain bootstrapped portably. Verify: all version commands succeed; `git check-attr eol -- scripts/judge0_smoke.sh` → `lf`. |
| D1-T1 Judge0 → **local sandbox** | ✅ DONE (re-scoped) | Judge0 dropped on the human's instruction (zero budget). Replaced with a real local Python sandbox — see *Zero-budget pivot* below. `judge0/HOSTED.md` + `scripts/judge0_smoke.sh` retained as the swap-back path. |
| D1-T2 Postgres, schema, seed | ✅ DONE | `docker-compose.yml` (postgres:16 + litellm), `01_schema.sql` (§7.1), `generate_two_sum.py` → `02_seed.sql` (155 KB). Verify: `bash db/verify.sh` → **21/21 PASS**. |
| D1-T3 Java domain service | ✅ DONE | Spring Boot 3.5.16 / Java 21, JdbcTemplate, internal-token filter, trace-id filter, `Sandbox` seam with local + Judge0 implementations. Verify: `bash domain/verify.sh` → **12 passed, 0 failed, 0 skipped**; `mvn test` → **13/13**. |
| D1-T4 Python orchestrator core | ✅ DONE | uv venv on Python 3.11.15; verifier, LLM client, domain client, verdict cache, LOGIC-phase nodes, graph on `MemorySaver`, CLI harness. Verify: `uv run pytest` → **49/49**; `cli_harness.py --fixtures` → **6/6** (table below). |
| 🚦 Day 1 gate | ✅ **REACHED** | Reported to the human. |
| D2-T1 Code phase in graph | ⬜ next | `execute_code`, `code_tutor`, `verify_code`, `finish`; hidden-test stripping; `code:` in the harness |
| D2-T2 PostgresSaver + FastAPI | ⬜ | |
| D2-T3 Rust gateway | ⬜ | Unblocked (cargo 1.98.1 + MSVC linker present) |
| D2-T4 Next.js UI | ⬜ | |
| 🚦 Day 2 gate | ⬜ | |
| D3-T1 Stretch | ⬜ | LLM judge; containerising app services (LiteLLM already containerised) |
| D3-T2 Demo tooling | ⬜ | |
| D3-T3 Cold start test | ⬜ | |
| D3-T4 Pre-warm | ⬜ | |
| D3-T5 Rehearsal support | ⬜ | |

## D1-T4 fixture verdict table (the mini golden set)

`cd orchestrator && uv run python scripts/cli_harness.py --fixtures`

| Id | Verdict | Approach | Misconception | Cache hit | Result | Turn time |
|---|---|---|---|---|---|---|
| F1 | FAIL | – | `nested-loop` | false | ✅ OK | 36.0 s |
| F2 (chat) | *(carries F1)* | – | `nested-loop` | false | ✅ tutor replied | 18.9 s |
| F3 | PASS | `lookup-single-pass` | – | false | ✅ phase → CODE | 39.1 s |
| F3b | PASS | `sort-two-pointer` | – | false | ✅ phase → CODE | 54.9 s |
| F6 (`"use hashmap"`) | FAIL | – | – | false | ✅ OK | 92.1 s |
| F3c (F3 in a fresh thread) | PASS | `lookup-single-pass` | – | **true** | ✅ no LLM call for the verdict | 30.7 s |

Every delivered tutor turn was checked against all 9 `forbidden_terms_logic_tutor` — **zero leaks**.
F1's reply, in the student's own Hinglish register:

> *"Agar array mein 20,000 numbers hon, toh tumhara approach kitne pairs check karega aur kya har pair ko dekhna sach mein zaroori hai?"*

## Zero-budget pivot (2026-09-21, human directive)

The human is a student on a strict $0.00 budget: no card for RapidAPI, no minimum balance on
OpenRouter. Three changes resulted.

### 1. Judge0 → local Python sandbox

`Sandbox` is now an interface with two implementations, chosen by `EXECUTOR_MODE`:

| Mode | Implementation | Cost | Network |
|---|---|---|---|
| **`LOCAL`** (default) | `LocalPythonSandbox` — runs student code in a subprocess | $0 | none |
| `JUDGE0` | `Judge0Client` — hosted Judge0 CE | metered | required |

Both report **Judge0 status ids**, so `BucketMapper` and the entire §8 table are byte-identical
either way and all 13 unit tests still apply. The Judge0 client stays compiled and tested as the
documented swap-back path, which keeps the §3 "only the base URL and headers change" claim true.

**A correction to the directive as written.** The instruction specified
*"status 13 (Time Limit Exceeded)"*. Status 13 is Judge0's **Internal Error**; TLE is **status 5**.
Our own bucket table maps 13 → `INFRA_ERROR` → *"The sandbox failed; this attempt does not count"*,
which routes around the code tutor entirely and would have killed the F4b demo beat. A timeout
reports **status 5**.

**Why real execution rather than the regex mock.** It costs the same ($0), needs no network, and
produces genuine `SyntaxError`, `KeyError`, timeouts and wrong answers — so an examiner can type
arbitrary code during Q&A and get a truthful verdict, where a pattern-matcher would confidently
lie. It also means we are not violating §1.5 ("never fake the hard parts").

**Isolation — stated honestly.** `LocalPythonSandbox` is *not* a security sandbox. Student code
runs with the service's privileges. It has: a hard timeout with `destroyForcibly` on the process
tree, a fresh temp dir per run, no shell, `-I` isolated mode, and truncated output capture. That is
appropriate for a single-user local demo and nothing more. This belongs on the deviations slide.

### 2. LiteLLM proxy reintroduced

`ghcr.io/berriai/litellm:main-latest` on port 4000, config in `litellm_config.yaml`. The
orchestrator asks for `logistream-evaluator` / `logistream-tutor` and never names a vendor.

It is **load-bearing, not decorative**: OpenRouter's free tier throws 429 constantly, and the very
first call through the proxy failed over to the backup model. A rate limit on stage is
unrecoverable by hand; LiteLLM makes it automatic.

### 3. Model choice by evidence (trap 12 landed)

**`google/gemini-2.0-flash-exp:free` no longer exists on OpenRouter.** `scripts/model_bakeoff.py`
scores candidates against the real F1/F3/F3b/F6 fixtures:

| Model | Verdicts | Valid JSON | Avg | Role |
|---|---|---|---|---|
| `qwen/qwen3.8-27b:free` | **4/4** | **4/4** | 18.1 s | **primary** |
| `nvidia/nemotron-3-super-120b-a12b:free` | 3/4 | 3/4 | 7.6 s | fallback |
| `z-ai/glm-5.2:free` | 1/4 | 1/4 | 17.7 s | rate-limited out |
| `google/gemma-4-31b-it:free` | 0/4 | 0/4 | 16.6 s | rate-limited out |

## Findings for the human

- **🔴 Turn latency is the new Risk #1.** Free-tier turns measured **18.9 s – 92.1 s**; CLAUDE.md
  budgeted 20–40 s. F6 at 92 s would be a painful silence on stage. Mitigations available, in order
  of value: (a) D3-T4 pre-warm — already proven, `cache_hit: true` works; (b) **also cache the
  summariser**, since F3c still cost 30.7 s on a verdict cache hit because `summarize_logic` makes
  its own LLM call; (c) keep the UI's live seconds counter prominent so the wait is legible.
  Recommend (a) + (b) on Day 3.
- **Free-tier 429s are frequent.** Two of four bake-off candidates were rate-limited out entirely.
  LiteLLM failover covers this, but back-to-back demo runs may still stall. The verdict cache is
  the real defence.
- **§6.4 gap closed** with the two approved narrow patterns, plus five false-positive guards
  asserting that ordinary tutoring prose ("Return the indices, not the values.") still passes.

## Open blockers

*(none)*

## Decisions

- **2026-09-21 · Shell = Git Bash.** §0.1 prefers WSL2 (Ubuntu); `wsl -l -v` lists only
  `docker-desktop`. Git Bash is the documented fallback. All repo scripts stay bash.
- **2026-09-21 · Toolchain is repo-pinned, not machine-installed.** winget has no Apache Maven
  package and its Temurin package is machine-scope (needs UAC, unavailable from this shell), so
  `scripts/bootstrap_toolchain.sh` downloads Temurin 21 and Maven 3.9.16 into `tools/` and installs
  rustup per-user. `scripts/env.sh` puts them on PATH and sets `JAVA_HOME`. No admin rights needed,
  and the Thursday demo cannot be broken by a machine-wide JDK change.
- **2026-09-21 · Orchestrator Python = 3.11.15 (uv-managed), not the PATH 3.14.7.** 3.11 is what
  the LangGraph / psycopg / pydantic wheel ecosystem is proven against.
- **2026-09-21 · The Java service runs in UTC.** pgjdbc puts the JVM's default zone id in the
  connection startup packet. On this host that is the legacy alias `Asia/Calcutta`, which
  `postgres:16`'s tzdata does not carry (only `Asia/Kolkata`), so **every** connection failed with
  `FATAL: invalid value for parameter "TimeZone"` before any query ran. `DomainApplication` pins the
  default zone to UTC in a static block; log timestamps carry a `Z` suffix.
- **2026-09-21 · Bucket mapping is a pure function.** `BucketMapper` is static and takes
  already-scored results, so all §8 rules — including the Python-`SyntaxError`-as-status-11
  reclassification — are unit-tested with no sandbox at all.
- **2026-09-21 · Test 5 uniqueness proven two ways.** The generator asserts `count_pairs == 1`;
  `db/verify.sh` independently re-derives it in SQL over all ~200M pairs. Measured: single-pass
  0.003 s, nested loop ~7 s against `cpu_time_limit=2`.
- **2026-09-21 · The verdict cache degrades to a no-op.** If Postgres is unreachable the cache logs
  a warning and continues. A cache outage must never take a session down mid-demo.

## Deviations from CLAUDE.md

| # | Deviation | Why | Impact |
|---|---|---|---|
| 1 | Shell is Git Bash, not WSL2 Ubuntu | No Ubuntu distro installed; §0.1 names Git Bash as the fallback | None. |
| 2 | Toolchain installed portably under `tools/` | winget has no Maven package; its Temurin needs UAC | None, and better: `JAVA_HOME` is per-repo, machine default untouched. |
| 3 | Orchestrator Python is 3.11.15, not the PATH 3.14.7 | Wheel-ecosystem maturity | None. |
| 4 | **Judge0 replaced by a local subprocess sandbox** | Zero budget; a metered third-party sandbox is a live-demo liability | Execution is real, free and offline. Not a security sandbox — **goes on the deviations slide**. |
| 5 | **LiteLLM reintroduced** (CLAUDE.md §3 had deferred it) | Free-tier 429s need automatic failover | Positive: restores the full-spec component and decouples model names from vendors. |
| 6 | Models are free-tier OpenRouter, not paid | Zero budget | Slower turns (18–92 s) and occasional 429s. See Risk #1 above. |
| 7 | §6.4 code-line rules tightened with two extra patterns | Human-approved 2026-09-21 | Closes the colonless `return [` / `import x` gap; guarded against prose false positives. |
