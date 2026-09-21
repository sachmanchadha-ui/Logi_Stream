"use client";

import type { Phase, SessionView } from "@/lib/types";

const STEPS: { id: Phase; label: string }[] = [
  { id: "LOGIC", label: "Logic" },
  { id: "CODE", label: "Code" },
  { id: "DONE", label: "Done" },
];

function stepState(step: Phase, current: Phase): "done" | "active" | "todo" {
  const order: Phase[] = ["LOGIC", "CODE", "DONE"];
  const a = order.indexOf(step);
  const b = order.indexOf(current);
  if (a < b) return "done";
  if (a === b) return "active";
  return "todo";
}

export function Header({
  view,
  busy,
  onReset,
}: {
  view: SessionView | null;
  busy: boolean;
  onReset: () => void;
}) {
  const phase = view?.phase ?? "LOGIC";

  return (
    <header className="flex items-center gap-6 border-b border-[var(--border)] bg-[var(--surface)] px-5 py-3">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-semibold tracking-tight">LogiStream</span>
        <span className="hidden text-xs text-[var(--muted)] sm:inline">
          logic before code
        </span>
      </div>

      <nav className="flex items-center gap-1" aria-label="Progress">
        {STEPS.map((step, i) => {
          const state = stepState(step.id, phase);
          return (
            <div key={step.id} className="flex items-center gap-1">
              {i > 0 && (
                <span
                  className={`h-px w-6 ${
                    state === "todo"
                      ? "bg-[var(--border)]"
                      : "bg-[var(--accent)]"
                  }`}
                />
              )}
              <span
                aria-current={state === "active" ? "step" : undefined}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  state === "active"
                    ? "bg-[var(--accent)] text-[#08101f]"
                    : state === "done"
                      ? "bg-[var(--surface-2)] text-[var(--accent)]"
                      : "bg-[var(--surface-2)] text-[var(--muted)]"
                }`}
              >
                {state === "done" ? "✓ " : ""}
                {step.label}
              </span>
            </div>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-4 text-xs text-[var(--muted)]">
        <span title="How many times logic and code have been submitted">
          attempts&nbsp;
          <span className="font-mono text-[var(--foreground)]">
            logic {view?.attempts.logic ?? 0} · code {view?.attempts.code ?? 0}
          </span>
        </span>
        <button
          onClick={onReset}
          disabled={busy}
          className="rounded border border-[var(--border)] px-3 py-1 text-xs text-[var(--foreground)] transition-colors hover:border-[var(--fail)] hover:text-[var(--fail)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Reset
        </button>
      </div>
    </header>
  );
}
