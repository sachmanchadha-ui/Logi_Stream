# Demo script — click by click

The §10 narrative, as steps you can follow on stage. Every step below was driven
end to end in a real browser during D2-T4 and behaved as described.

## Before you start

```bash
cd /g/fsjp_project_completed
set -a; source .env; set +a
source scripts/env.sh
```

Five things must be up. Check all of them:

| Port | Service | Check |
|---|---|---|
| 5432 | Postgres | `docker compose ps` |
| 4000 | LiteLLM | `curl -s localhost:4000/health/liveliness` |
| 8080 | Java domain | `curl -s localhost:8080/health` |
| 8001 | Python orchestrator | `curl -s localhost:8001/health` |
| 8000 | Rust gateway | `curl -s localhost:8000/health` |
| 3000 | Next.js UI | open http://localhost:3000 |

Open the browser **maximised**. Below about 770 px wide the layout stacks to a
single column, which still works but wastes the split-pane effect.

Press **Reset** before you begin, so the attempt counters start at 0.

---

## The run

### 1 · F1 — the tutor refuses to hand over the answer

Paste into the left textarea and click **Submit logic**:

> Main har number ke liye baaki saare numbers check karunga, do loops laga ke. Jab dono ka sum target ke barabar ho jaye toh unke index return kar dunga.

*What to expect:* the busy bar reads **"Evaluating your logic…"** with a live
seconds counter. After roughly 15–40 s the tutor panel opens by itself with a
question in Hinglish about how many pairs 20,000 numbers would need.

**Say:** it never names the technique. It cannot — every tutor turn is checked
by a deterministic verifier before the student sees it.

### 2 · Open "Under the hood"

Click the bar at the bottom.

*What to expect:* `verdict FAIL`, `misconception nested-loop`, `confidence 0.98`,
the violated invariant *"is faster than checking every pair"*, and the node path.

**Say:** this is a structured diagnosis, not a chat reply. The misconception id
is what routes the tutor. The evaluator also writes a free-text rationale — it
is logged server-side and deliberately never sent to the browser.

### 3 · F2 — the conversation continues

Type into the tutor panel and press **Send**:

> 20,000 numbers pe toh lagbhag 20 crore pairs ho jayenge. Kya main pehle dekhe hue numbers kahin yaad rakh sakta hoon?

*What to expect:* **"Tutor is thinking…"**, then a reply that encourages without
naming the data structure.

### 4 · Refresh the page

Press **F5** / **Ctrl-R**.

*What to expect:* the whole conversation is still there, verdict included.

**Say:** the session is one long-running LangGraph graph checkpointed to
Postgres. We killed the Python process mid-conversation during testing and the
transcript survived that too.

### 5 · F3 — the gate opens

Replace the textarea contents and submit:

> Main array ko ek hi baar traverse karunga. Har number ke liye dekhunga ki target minus current number pehle aa chuka hai ya nahi — uske liye ek lookup rakhunga jismein value se uska index mil jaye. Agar mil gaya toh dono indices return kar dunga, warna current number aur uska index lookup mein daal dunga. Check pehle hota hai aur insert baad mein, isliye same element do baar use nahi hoga.

*What to expect:* verdict **PASS**, `matched_approach lookup-single-pass`, the
stepper ticks **Logic** and moves to **Code**, a *"Your accepted logic"* tab
appears on the left, and the Monaco editor replaces the textarea.

**Say:** they never used the word for the data structure. They described the
mechanism, which is what we grade.

### 6 · F4 — the sandbox catches a real error

Type into the editor and click **Run & submit**:

```python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        j = seen[target - x]
        return [j, i]
```

*What to expect:* **"Running tests in the sandbox…"**, then a drawer showing
`RUNTIME_ERROR`, 0/5 passed. Tests 1 and 2 are marked **public** and expand to
show input, expected and actual. Tests 3, 4 and 5 are **hidden** and show only a
label and a status.

The tutor explains the `KeyError` in terms of the student's own accepted
algorithm, quotes their own line back, and does not write the fix.

**Say:** the hidden tests' inputs are stripped twice over — once before the
browser, and once before the tutor's own context window. A model that has seen
them would eventually quote them.

**If "Under the hood" shows `regenerations 1`:** that is worth pointing at. The
verifier rejected the tutor's first draft (during our run: *"draft is 161 words,
limit is 160"*) and made it write another one.

### 7 · F5 — success

Replace the code and run again:

```python
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
```

*What to expect:* `ACCEPTED`, **5/5 passed** — including the 20,000-element
hidden test in well under a second — the stepper reaches **Done**, and the node
path reads `await_input → execute_code → finish`.

---

## Kept back for questions

| Fixture | Input | Shows |
|---|---|---|
| **F3b** | the sort + two-pointer description in `demo/fixtures/logic_f3b.txt` | a different valid approach also passes (`matched_approach sort-two-pointer`) |
| **F4b** | `demo/fixtures/code_tle.py` | the nested loop times out on the 20,000 case; the tutor talks about scale |
| **F6** | just `use hashmap` | **FAIL** — naming a technique is not describing an algorithm |

## If something goes wrong

| Symptom | What to do |
|---|---|
| A turn takes 90 s | Normal on the free LLM tier. The seconds counter is visible; talk over it. The verdict cache makes repeats much faster. |
| Red error bar `0: Cannot reach the gateway` | The Rust gateway is down. Restart it; the session survives. |
| `502` / `504` | An upstream is down. Check :8001 and :8080. |
| The tutor answers with the canned fallback | The verifier rejected `MAX_REGENERATIONS` drafts. It is working as designed — say so. |
| Everything is wedged | **Reset**, then re-run from step 1. Never `docker compose down -v`: it wipes the verdict cache and the checkpoints. |
