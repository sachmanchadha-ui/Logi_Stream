# Judge0 — hosted mode

`JUDGE0_MODE=HOSTED_API`

## Why hosted and not self-hosted

Judge0's sandbox (isolate) requires cgroup v1. This machine is Windows + Docker
Desktop and `docker info` reports:

```
Docker version 29.8.0 ... CgroupVersion 2
```

Docker Desktop cannot be switched back to cgroup v1 reliably, so self-hosting was
ruled out before Day 1 (CLAUDE.md §0.1) and no spike was attempted.

**The architecture is unchanged.** Java still owns all execution; Python never
calls Judge0. Only Java's base URL and request headers differ from the self-hosted
design, which is exactly the seam listed in the deviations table (§3).

## Endpoint and headers

| Setting | Value |
|---|---|
| `JUDGE0_URL` | `https://judge0-ce.p.rapidapi.com` |
| `JUDGE0_RAPIDAPI_HOST` | `judge0-ce.p.rapidapi.com` |
| `JUDGE0_RAPIDAPI_KEY` | from the RapidAPI dashboard — **never committed** |

Every request carries:

```
X-RapidAPI-Key:  $JUDGE0_RAPIDAPI_KEY
X-RapidAPI-Host: $JUDGE0_RAPIDAPI_HOST
Content-Type:    application/json      (on POST)
```

## Calls we make

Only two endpoints are used.

**Submit** — all tests for one run go in a single batch:

```
POST /submissions/batch?base64_encoded=true
{"submissions": [ { language_id, source_code, stdin,
                    cpu_time_limit, wall_time_limit, memory_limit }, ... ]}
```

**Poll** — one request covers the whole batch:

```
GET /submissions/batch?tokens=<t1,t2,...>&base64_encoded=true
    &fields=token,status_id,status,stdout,stderr,compile_output,time
```

Polled every `JUDGE0_POLL_INTERVAL_MS` (1000) for at most `JUDGE0_MAX_POLLS`
(15). Anything still in status 1 (In Queue) or 2 (Processing) after that is
`INFRA_ERROR`.

### Rules that are easy to get wrong

- **`base64_encoded=true` in both directions.** Source, stdin, stdout, stderr and
  compile_output are all base64. Decode in Java. This avoids UTF-8 failures on
  Hinglish comments or odd bytes in student output (trap 9).
- **Never send `expected_output`.** Java compares `stdout.strip()` to
  `expected_output.strip()` itself. Letting Judge0 do the comparison introduces
  its own whitespace semantics, which we do not want to depend on.
- **`fields=` is mandatory in practice.** Without it the poll returns every
  column for every submission, which is a lot of base64 for the 150 KB test 5.
- **Python has no compile step**, so a `SyntaxError` comes back as status 11
  (Runtime Error / NZEC), not status 6. Java reclassifies status 11 whose stderr
  contains `SyntaxError` or `IndentationError` as `COMPILE_ERROR` (§8). Without
  that rule the syntax-error demo path never fires.
- **Language id**: `JUDGE0_PYTHON_LANGUAGE_ID=71` is the expected Python 3 id.
  `scripts/judge0_smoke.sh` confirms it against `GET /languages` and warns if the
  listing offers a different one.

## Quota discipline

**Every submit and every poll is a billed request.** One code run costs
`1 + (number of polls)` requests — typically 2–4, worst case 16.

Rules:

- No automatic retries beyond the single infra retry in the §8 bucket table.
- Every script that touches Judge0 prints the number of requests it used.
- Java logs a running request counter per run.
- `demo/healthcheck.sh` only submits when called with `--judge0`, because a
  health check that silently burns quota before a demo is a trap.

Budget consumers, in rough order of appetite: `domain/verify.sh` (7 execute
runs), rehearsals, and the D3-T3 cold-start run.

### Plan limit

| Field | Value |
|---|---|
| RapidAPI plan | _TBD — record after D1-T1_ |
| Daily request limit | _TBD_ |
| Confirmed language id | _TBD_ |

> Fill this in from the RapidAPI dashboard when the key lands. If the free tier's
> daily limit is small, subscribe to the cheapest paid tier for Wednesday and
> Thursday — a rate limit on stage is unrecoverable (CLAUDE.md §12).

## Smoke test

```bash
source scripts/env.sh
bash scripts/judge0_smoke.sh
```

Does one `/languages` call, one batch submit of `print("hello")`, and polls per
the rules above. Asserts status 3 and stdout `hello`, then prints its request
count. Exits 2 if `JUDGE0_RAPIDAPI_KEY` is unset.

## Failure modes seen from the client side

| Symptom | Meaning |
|---|---|
| 401 / 403 on `/languages` | key wrong, or not subscribed to **Judge0 CE** specifically |
| 429 | daily or per-minute quota exhausted — stop and check the dashboard |
| status stuck at 1/2 past 15 polls | Judge0 side is backed up → `INFRA_ERROR`, attempt does not count |
| status 13 / 14 | internal error / exec format error → `INFRA_ERROR` after one full batch retry |
