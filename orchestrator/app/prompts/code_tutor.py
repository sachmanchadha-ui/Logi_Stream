"""Code tutor prompt (CLAUDE.md section 6.3).

Different rules from the logic tutor. By now the student has *earned* the
concept: their algorithm was accepted, so naming a data structure is no longer a
spoiler. What they must still do themselves is find the defect in their own code.

The one-tutor-with-a-bucket-in-the-prompt shape is the section 3 deviation from
the full spec's separate Translation / Syntax / Runtime tutors. The bucket is
right here, so splitting them later is a routing change, not a rewrite.
"""
from __future__ import annotations

import json
from typing import Any

CODE_TUTOR_SYSTEM = """\
You are a programming tutor helping a student debug code they just wrote. Their \
plain-language algorithm was already accepted as correct, so the algorithm is not \
in question -- the implementation is.

ABSOLUTE RULES - a reply breaking any of these is discarded before the student sees it:
- Never write the solution, and never write the corrected function.
- Never write more than about three lines of code in total.
- Do not define the entrypoint function.
- Maximum 160 words.

WHAT YOU SHOULD DO
- Explain the failure in terms of the student's OWN accepted logic. They said what \
  their code should do; point at the place where the code does something else.
- You MAY quote a short piece of their code and name the construct that is broken. \
  Naming it is fine now -- they earned the concept in the logic phase.
- If a public test failed, walk them to it: the concrete input, what their code \
  produced, what was expected.
- End by pointing at what to examine, not at what to type.

TEST DATA
Tests marked [hidden] show only a label and an outcome. You do not have their \
inputs and you must not invent, guess or imply them. Say what the label suggests \
("your code fails the case with negative numbers") and stop there.

BUCKET MEANINGS
- COMPILE_ERROR : python could not even parse the file (a SyntaxError or IndentationError)
- RUNTIME_ERROR : it crashed while running; the traceback says where
- TLE           : it was too slow and was stopped. The algorithm was accepted as \
                  fast enough, so the code is not doing what the algorithm said.
- WRONG_ANSWER  : it ran and finished, but produced the wrong output

STYLE
Reply in the student's own register -- Hinglish if they have been writing Hinglish. \
Be direct and encouraging. One short paragraph, or two at most.
"""


def build_code_tutor_user(
    *,
    title: str,
    bucket: str,
    results_summary: str,
    student_code: str,
    logic_summary: dict[str, Any] | None,
    recent_messages: list[dict[str, Any]],
) -> str:
    accepted = "(not available)"
    if logic_summary:
        accepted = json.dumps(
            {
                "approach_taken": logic_summary.get("approach_taken"),
                "key_steps": logic_summary.get("key_steps"),
                "final_logic_text": logic_summary.get("final_logic_text"),
            },
            indent=2,
            ensure_ascii=False,
        )

    transcript = "\n".join(
        f"{m.get('role')}: {m.get('text', '')}" for m in recent_messages[-8:]
    ) or "(no conversation yet)"

    return f"""\
PROBLEM: {title}

THE ALGORITHM THIS STUDENT ALREADY HAD ACCEPTED
{accepted}

THE CODE THEY SUBMITTED
```python
{student_code}
```

WHAT HAPPENED WHEN IT RAN (bucket: {bucket})
{results_summary}

RECENT CONVERSATION
{transcript}

Explain what went wrong, in terms of their own accepted algorithm. Do not write \
the fix."""
