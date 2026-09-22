"use client";

import { useEffect, useRef, useState } from "react";
import type { Message } from "@/lib/types";

/**
 * Floating Socratic chat over the right pane. Opens automatically when a tutor
 * message arrives, because the tutor's question is the product -- if the
 * student has to go looking for it, the whole premise is buried.
 */
export function ChatPanel({
  messages,
  open,
  onOpenChange,
  onSend,
  busy,
  disabled,
  done,
}: {
  messages: Message[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSend: (text: string) => void;
  busy: boolean;
  /** input is unusable right now (busy OR finished) */
  disabled: boolean;
  /** the session is actually over - only this changes the placeholder */
  done: boolean;
}) {
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);

  const conversation = messages.filter(
    (m) => m.kind === "hint" || m.kind === "chat" || m.kind === "info",
  );

  useEffect(() => {
    if (open && scroller.current) {
      scroller.current.scrollTop = scroller.current.scrollHeight;
    }
  }, [open, conversation.length, busy]);

  const tutorCount = messages.filter((m) => m.role === "tutor").length;

  if (!open) {
    return (
      <button
        onClick={() => onOpenChange(true)}
        className="absolute bottom-4 right-4 z-20 flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-4 py-2 text-xs shadow-lg transition-colors hover:border-[var(--accent)]"
      >
        Tutor
        {tutorCount > 0 && (
          <span className="rounded-full bg-[var(--accent)] px-1.5 text-[10px] text-[var(--on-accent)]">
            {tutorCount}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="absolute bottom-4 right-4 z-20 flex h-[26rem] w-[24rem] max-w-[calc(100%-2rem)] flex-col rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-2xl">
      <div className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 py-2">
        <span className="text-xs font-semibold">Socratic tutor</span>
        <span className="text-[10px] text-[var(--muted)]">
          asks questions, never gives the answer
        </span>
        <button
          onClick={() => onOpenChange(false)}
          className="ml-auto text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
          aria-label="Close tutor panel"
        >
          ✕
        </button>
      </div>

      <div
        ref={scroller}
        className="scroll-thin min-h-0 flex-1 space-y-3 overflow-y-auto p-3"
      >
        {conversation.length === 0 && (
          <p className="text-xs text-[var(--muted)]">
            Submit your logic and the tutor will respond here.
          </p>
        )}
        {conversation.map((m, i) => (
          <div
            key={i}
            className={`text-xs leading-relaxed ${
              m.role === "student" ? "text-right" : ""
            }`}
          >
            <span
              className={`inline-block max-w-[90%] whitespace-pre-wrap rounded-lg px-3 py-2 text-left ${
                m.role === "tutor"
                  ? "bg-[var(--surface-2)]"
                  : m.role === "system"
                    ? "border border-[var(--border)] text-[var(--muted)]"
                    : "bg-[var(--accent)] text-[var(--on-accent)]"
              }`}
            >
              {m.text}
            </span>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-1 px-1 text-xs text-[var(--muted)]">
            <span className="dot">●</span>
            <span className="dot">●</span>
            <span className="dot">●</span>
          </div>
        )}
      </div>

      <form
        className="flex shrink-0 gap-2 border-t border-[var(--border)] p-2"
        onSubmit={(e) => {
          e.preventDefault();
          const text = draft.trim();
          if (!text || busy || disabled) return;
          onSend(text);
          setDraft("");
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy || disabled}
          // only `done` may say "finished" -- keying this off `disabled` made a
          // slow turn look like the session had ended
          placeholder={done ? "This session is finished." : "Ask the tutor…"}
          className="min-w-0 flex-1 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-xs outline-none focus:border-[var(--accent)] disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || disabled || !draft.trim()}
          className="rounded bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-[var(--on-accent)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  );
}
