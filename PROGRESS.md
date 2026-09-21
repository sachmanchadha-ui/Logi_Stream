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
| Java | **26.0.2 only** (no JAVA_HOME set) — see blocker B3 |
| Maven | **MISSING** — blocker B1 |
| Rust / cargo | **MISSING** — blocker B2 |
| psql client | not on PATH (not required; use `docker compose exec postgres psql`) |
| Package managers available | `winget` 1.29.290, `choco` 2.7.3, `uv` 0.11.32 |

## Task log

| Task | Status | Notes |
|---|---|---|
| D1-T0 Toolchain and skeleton | ⏸ BLOCKED (scaffolding done) | Layout, `.gitattributes`, `.gitignore`, `.env.example`, `PROGRESS.md`, `git init` done. Verify fails on missing Maven + Rust. STOPPED per §1.4 / D1-T0 instruction. |
| D1-T1 Hosted Judge0 setup | ⬜ not started | Needs `JUDGE0_RAPIDAPI_KEY` from the human in `.env` |
| D1-T2 Postgres, schema, seed | ⬜ not started | Not blocked — Docker is up |
| D1-T3 Java domain service | ⬜ not started | Blocked on Maven (B1) and JDK decision (B3) |
| D1-T4 Python orchestrator core | ⬜ not started | Needs `OPENROUTER_API_KEY` + a verified paid model slug |
| 🚦 Day 1 gate | ⬜ | |
| D2-T1 Code phase in graph | ⬜ | |
| D2-T2 PostgresSaver + FastAPI | ⬜ | |
| D2-T3 Rust gateway | ⬜ | Blocked on Rust (B2) |
| D2-T4 Next.js UI | ⬜ | |
| 🚦 Day 2 gate | ⬜ | |
| D3-T1 Stretch | ⬜ | |
| D3-T2 Demo tooling | ⬜ | |
| D3-T3 Cold start test | ⬜ | |
| D3-T4 Pre-warm | ⬜ | |
| D3-T5 Rehearsal support | ⬜ | |

## Open blockers

- **B1 — Maven missing.** Required by D1-T3 (today). Install: `winget install -e --id Apache.Maven` (then reopen the shell).
- **B2 — Rust missing.** Required by D2-T3 (Wednesday), not today. Install: `winget install -e --id Rustlang.Rustup` (then reopen the shell).
- **B3 — Only JDK 26 installed.** Spring Boot 3 targets Java 17–21 LTS; running its build and bytecode tooling on a JDK two releases past the newest LTS is an avoidable risk on a 3-day deadline. Recommendation: install Temurin 21 and point `JAVA_HOME` at it for this repo only — `winget install -e --id EclipseAdoptium.Temurin.21.JDK`. Java 26 stays the machine default.
- **B4 — Secrets not yet provided.** `.env` needs `JUDGE0_RAPIDAPI_KEY` (D1-T1) and `OPENROUTER_API_KEY` + `LLM_MODEL_EVALUATOR` / `LLM_MODEL_TUTOR` slugs (D1-T4).

## Decisions

- **2026-09-21 · Shell = Git Bash.** §0.1 prefers WSL2 (Ubuntu); `wsl -l -v` lists only `docker-desktop`. Git Bash is the documented fallback. All repo scripts stay bash.
- **2026-09-21 · Judge0 = HOSTED_API confirmed on this machine.** `docker info` reports `CgroupVersion 2`, exactly as §0.1 predicted. No self-hosting spike attempted.
- **2026-09-21 · Orchestrator Python = 3.11.15 (uv-managed), not the PATH 3.14.7.** CLAUDE.md says 3.11+; 3.11 is what the LangGraph / psycopg / pydantic wheel ecosystem is proven against, and a missing wheel on 3.14 would burn build time we do not have.

## Deviations from CLAUDE.md

*(none yet)*
