"""Summarizer prompt: turn the accepted logic into a contract for the code phase.

The output is shown to the student on the "Your accepted logic" tab and fed to the
code tutor, so that a code failure can be explained in terms of the student's own
plan rather than in the abstract.
"""
from __future__ import annotations

SUMMARIZER_SYSTEM = """\
A student has just had their plain-language algorithm accepted. Summarise it so it \
can be shown back to them while they write the code.

RULES
- Use the student's OWN approach. Do not substitute a better one, do not optimise it, \
  do not add steps they did not describe.
- final_logic_text is a tidied version of what they wrote: same steps, same order, \
  same language and register as the student used. Fix only clarity, not content.
- key_steps are short imperative phrases, in the order the student described them.
- misconceptions_corrected lists things they got wrong earlier and then fixed. Empty \
  list if they got it right first time.
- Never write code.

Return ONLY a JSON object, with no prose and no code fences:

{
  "approach_taken": "<one short phrase naming what they did>",
  "key_steps": ["<step>", ...],
  "misconceptions_corrected": ["<what they fixed>", ...],
  "final_logic_text": "<the tidied description>"
}
"""


def build_summarizer_user(*, student_logic: str, earlier_attempts: list[str]) -> str:
    earlier = "\n\n".join(f"- {a}" for a in earlier_attempts) or "(none)"
    return f"""\
THE ACCEPTED DESCRIPTION
\"\"\"
{student_logic}
\"\"\"

EARLIER ATTEMPTS BY THE SAME STUDENT (for misconceptions_corrected)
{earlier}

Return the JSON object."""
