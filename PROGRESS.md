# PROGRESS — LogiStream 3-Day MVP

Task log, decisions and deviations. Updated after every task (see CLAUDE.md §1).

## Environment facts (established D1-T0, 2026-09-21)

| Fact | Value |
|---|---|
| Repo root | `G:\fsjp_project_completed` |
| Shell | **Git Bash (MINGW64)** — WSL2 has no Ubuntu distro, only the internal `docker-desktop` one (§0.1 fallback) |
| Docker | 29.8.0, Compose v5.5.1, daemon up, **`CgroupVersion 2`** → confirms `JUDGE0_MODE=HOSTED_API` (§0.1) |
| Node | v26.5.0 (npm 11.17.0) — OK (≥ 20) |
| Python (PATH) | 3.14.7 |
| Python (uv) | **3.11.15** via `uv` 0.11.32 → orchestrator venv will be pinned to 3.11, not 3.14 |
| Java | **Temurin 21.0.12.1 LTS** in `tools/jdk21`, pinned via `scripts/env.sh`. Machine default (26.0.2) untouched |
| Maven | **3.9.16** in `tools/maven` |
| Rust / cargo | **1.98.1** (rustup, per-user `~/.cargo`) |
| MSVC linker | present (Visual Studio 18) — `cargo` can link on this box |
| psql client | not on PATH (not required; use `docker compose exec postgres psql`) |
| Package managers available | `winget` 1.29.290, `choco` 2.7.3, `uv` 0.11.32 |

## Task log

| Task | Status | Notes |
|---|---|---|
| D1-T0 Toolchain and skeleton | ✅ DONE | Layout per §4, `.gitattributes` (LF), `.gitignore`, `.env.example`, `git init`. Toolchain bootstrapped portably (see decision below). Verify: all version commands succeed; `git check-attr eol -- scripts/judge0_smoke.sh` → `lf`. |
| D1-T1 Hosted Judge0 setup | ⏸ BLOCKED on key | `judge0/HOSTED.md` and `scripts/judge0_smoke.sh` written; script syntax-checked and exits 2 cleanly with no key. **Cannot run the smoke test until `JUDGE0_RAPIDAPI_KEY` is in `.env`** — STOPPED per D1-T1. |
| D1-T2 Postgres, schema, seed | ✅ DONE | `docker-compose.yml` (postgres:16, named volume, `db/init` mounted), `01_schema.sql` (§7.1), `generate_two_sum.py` → `02_seed.sql` (155 KB). Verify: `bash db/verify.sh` → **21/21 PASS**. |
| D1-T3 Java domain service | 🟡 BUILT, partly verified | Spring Boot 3.5.16 on Java 21, JdbcTemplate, internal-token filter, trace-id filter, Judge0 client + bucket mapper. Verify: `bash domain/verify.sh` → **7 passed, 0 failed, 5 skipped**. The 5 skipped are the execution checks and need `JUDGE0_RAPIDAPI_KEY`. Unit tests: **13/13** on the §8 bucket table. |
| D1-T4 Python orchestrator core | 🟡 verifier done, rest blocked | uv venv on **Python 3.11.15**; langgraph 1.2.12, openai 3.16.2, fastapi 0.141.1, psycopg 3.3.6 pinned in `uv.lock`. `app/verifier.py` complete per §6.4 + fallbacks. Verify: `uv run pytest` → **42/42 PASS**. Remaining (llm.py, domain_client, state, nodes, graph, cli_harness) needs `OPENROUTER_API_KEY`. |
| 🚦 Day 1 gate | ⬜ | |
| D2-T1 Code phase in graph | ⬜ | |
| D2-T2 PostgresSaver + FastAPI | ⬜ | |
| D2-T3 Rust gateway | ⬜ | Unblocked (cargo 1.98.1 + MSVC linker present) |
| D2-T4 Next.js UI | ⬜ | |
| 🚦 Day 2 gate | ⬜ | |
| D3-T1 Stretch | ⬜ | |
| D3-T2 Demo tooling | ⬜ | |
| D3-T3 Cold start test | ⬜ | |
| D3-T4 Pre-warm | ⬜ | |
| D3-T5 Rehearsal support | ⬜ | |

## Findings for the human

- **§6.4's code-line regex has a gap.** The specified pattern
  `^\s*(def|for|while|if|elif|return|import|class)\b.*:\s*$` requires a trailing colon, so a bare
  `return [i, j]` or `import json` on its own line is **not** rejected in the logic phase. In practice such a
  line almost always arrives inside a code fence, which *is* caught, so exposure is small — and tightening the
  rule risks false positives on ordinary prose ("Return the indices, not the values."). Tightening it changes
  §6.4, which needs approval (§1.4), so it is left as specified. `test_known_gap_colonless_code_lines_are_not_caught`
  pins the current behaviour so the gap stays visible. **Decision needed at the Day 1 gate:** leave as-is, or add
  the narrow patterns `^\s*return\s*[\[\(]` and `^\s*import\s+\w+\s*$`.

## Open blockers

- ~~B1 Maven~~ / ~~B2 Rust~~ / ~~B3 JDK~~ — all resolved by `scripts/bootstrap_toolchain.sh` (2026-09-21).
- **B4 — Secrets not yet provided.** Blocks D1-T1 and D1-T4. `.env` needs:
  - `JUDGE0_RAPIDAPI_KEY` — RapidAPI dashboard, Judge0 CE subscription (D1-T1)
  - `OPENROUTER_API_KEY` (D1-T4)
  - `LLM_MODEL_EVALUATOR` / `LLM_MODEL_TUTOR` — a **paid** slug verified to exist on openrouter.ai/models (trap 12)

## Decisions

- **2026-09-21 · Shell = Git Bash.** §0.1 prefers WSL2 (Ubuntu); `wsl -l -v` lists only `docker-desktop`. Git Bash is the documented fallback. All repo scripts stay bash.
- **2026-09-21 · Judge0 = HOSTED_API confirmed on this machine.** `docker info` reports `CgroupVersion 2`, exactly as §0.1 predicted. No self-hosting spike attempted.
- **2026-09-21 · Orchestrator Python = 3.11.15 (uv-managed), not the PATH 3.14.7.** CLAUDE.md says 3.11+; 3.11 is what the LangGraph / psycopg / pydantic wheel ecosystem is proven against, and a missing wheel on 3.14 would burn build time we do not have.

- **2026-09-21 · Toolchain is repo-pinned, not machine-installed.** `scripts/bootstrap_toolchain.sh` downloads Temurin 21 and Maven 3.9.16 into `tools/` and installs rustup per-user. `scripts/env.sh` puts them on PATH and sets `JAVA_HOME`. Every start/verify script sources it. Rationale: no admin rights needed, and the Thursday demo cannot be broken by a machine-wide JDK change.
- **2026-09-21 · The Java service runs in UTC.** The Postgres JDBC driver puts the JVM's default zone id in the connection startup packet. On this host that id is the legacy alias `Asia/Calcutta`, which `postgres:16`'s tzdata does not carry (it has only `Asia/Kolkata`), so **every** connection failed with `FATAL: invalid value for parameter "TimeZone"` before any query ran. `DomainApplication` pins the default zone to UTC in a static block. All columns are `timestamptz`, the service never formats local time, and this removes the host locale from the demo. Java log timestamps carry a `Z` suffix so nobody misreads them during rehearsal.
- **2026-09-21 · Judge0 bucket mapping is a pure function.** `BucketMapper` is static and takes already-scored results, so all 13 §8 rules — including the Python-`SyntaxError`-as-status-11 reclassification — are unit-tested without spending a single Judge0 request.
- **2026-09-21 · Test 5 uniqueness proven two ways.** The generator asserts `count_pairs == 1` in Python; `db/verify.sh` independently re-derives it in SQL with a self-join over all ~200M pairs. Measured locally: single-pass 0.003 s, nested loop ~7 s against `cpu_time_limit=2` — a comfortable TLE margin for D1-T3.

## Deviations from CLAUDE.md

| # | Deviation | Why | Impact |
|---|---|---|---|
| 1 | Shell is Git Bash, not WSL2 Ubuntu | No Ubuntu distro installed; §0.1 names Git Bash as the fallback | None. All scripts stay bash with LF endings. |
| 2 | Toolchain installed portably under `tools/` (gitignored) instead of via `winget` | winget has no Apache Maven package at all, and its Temurin package is machine-scope (needs UAC, unavailable from this shell) | None, and it is better: `JAVA_HOME` is pinned per-repo by `scripts/env.sh`, so the machine default JDK 26 is untouched. Reproducible via `scripts/bootstrap_toolchain.sh`. |
| 3 | Orchestrator Python will be 3.11.15 (uv-managed), not the PATH 3.14.7 | CLAUDE.md says 3.11+; 3.11 is what LangGraph / psycopg / pydantic wheels are proven against | None. |
