# Thursday morning — the checklist

Start **30 minutes early**. Everything below is a command you can copy.

```bash
cd /g/fsjp_project_completed
```

---

## 1 · Bring it up  (~1 min)

```bash
bash demo/start.sh
```

Cold start from nothing measured at **53 s**. If everything is already running it
returns in about 3 s and changes nothing.

If it says Docker did not start, open Docker Desktop yourself, wait for the whale
to stop animating, and run it again.

## 2 · Check it  (~10 s)

```bash
bash demo/healthcheck.sh
```

Want **`READY`**. If the verdict cache warning appears, do step 3. Anything red:
see *If something is broken* below.

## 3 · Warm the caches — only if the health check warned  (~2 min)

```bash
cd orchestrator && uv run python ../demo/prewarm.py && cd ..
```

This is what makes the scripted beats fast (F3 goes from ~16 s to ~2.5 s). It
also leaves the session reset.

> ⚠️ **Never run `docker compose down -v`.** It destroys the volume holding the
> cache and the checkpoints, and you would have to redo this. `demo/stop.sh` is
> safe and deliberately has no flag that can do it.

## 4 · One scripted run to prove it  (~1–2 min)

```bash
bash demo/rehearse.sh
```

Drives F1 → F5 through the gateway, exactly the path the browser takes, and
prints the timing of each beat. Want **`REHEARSAL GREEN`**. It resets the session
when it finishes.

## 5 · Open the UI

```
http://localhost:3000
```

**Maximise the window.** Below ~770 px the layout collapses to one column — it
works, but you lose the split-pane effect the demo depends on.

Press **Reset** so the attempt counters read `logic 0 · code 0`.

## 6 · Present

Follow **`demo/SCRIPT.md`** — click-by-click, with what to say at each beat.

---

## Keep these open in other tabs

| What | Why |
|---|---|
| `demo/DEVIATIONS.md` | the "what we cut and why" slide |
| A terminal running `tail -f demo/logs/orchestrator.log` | shows the graph node transitions live, if anyone asks |
| The backup screen recording | if the network dies |

---

## If something is broken

| Symptom | Fix |
|---|---|
| A turn takes 60–90 s | Normal on the free tier for tutor replies, which are never cached. The UI shows a live seconds counter — talk over it. |
| Red bar: `Cannot reach the gateway` | `bash demo/start.sh` — it restarts only what is down. The session survives. |
| `502` or `504` in the UI | An upstream died. `bash demo/start.sh` again, then reload the page. |
| Tutor gives the same canned question twice | The verifier rejected the drafts and fell back. This is the safety net working — say so, it is a feature. |
| A verdict looks wrong | The free-tier model occasionally misjudges novel input. Press Reset and use a scripted fixture. |
| Completely wedged | `bash demo/stop.sh` then `bash demo/start.sh`. **Not** `down -v`. |
| No internet | Execution still works — it is local. The LLM does not. Switch to the recording. |

---

## The three things worth saying

1. **The tutor is prevented from answering, not asked not to.** Every turn is
   machine-checked before the student sees it. Open "Under the hood" and show
   `regenerations` and `verifier rejections` when they appear.

2. **Hidden tests are stripped twice** — once before the browser, once before the
   tutor's own context window.

3. **The code really runs.** Real `SyntaxError`, real `KeyError`, a real timeout.
   Invite someone to type something and break it.
