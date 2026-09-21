"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { ProblemPane } from "@/components/ProblemPane";
import { TestDrawer } from "@/components/TestDrawer";
import { UnderTheHood } from "@/components/UnderTheHood";
import { BusyBar, WorkPane } from "@/components/WorkPane";
import { ApiError, api } from "@/lib/api";
import type { Problem, SessionView } from "@/lib/types";

const PROBLEM_ID = "two-sum";

type BusyKind = "logic" | "chat" | "code" | "reset" | "load" | null;

const BUSY_LABEL: Record<Exclude<BusyKind, null>, string> = {
  logic: "Evaluating your logic…",
  chat: "Tutor is thinking…",
  code: "Running tests in the sandbox…",
  reset: "Resetting the session…",
  load: "Loading your session…",
};

export default function Page() {
  const [problem, setProblem] = useState<Problem | null>(null);
  const [view, setView] = useState<SessionView | null>(null);
  const [busy, setBusy] = useState<BusyKind>(null);
  const [busySince, setBusySince] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);

  const lastTutorCount = useRef(0);

  const begin = (kind: Exclude<BusyKind, null>) => {
    setBusy(kind);
    setBusySince(Date.now());
    setError(null);
  };

  const fail = (e: unknown) => {
    if (e instanceof ApiError) {
      setError(
        e.status ? `${e.status}: ${e.message}` : e.message,
      );
    } else {
      setError(String(e));
    }
  };

  // On load: fetch the problem and resume (or begin) the session. A refresh
  // must land back in the same conversation -- that is the checkpointing claim,
  // and the demo shows it by refreshing the page mid-flow.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      begin("load");
      try {
        const [p, v] = await Promise.all([
          api.getProblem(PROBLEM_ID),
          api.start(PROBLEM_ID),
        ]);
        if (cancelled) return;
        setProblem(p);
        setView(v);
        lastTutorCount.current = v.messages.filter(
          (m) => m.role === "tutor",
        ).length;
      } catch (e) {
        if (!cancelled) fail(e);
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // open the chat by itself whenever a NEW tutor message arrives
  useEffect(() => {
    if (!view) return;
    const tutors = view.messages.filter((m) => m.role === "tutor").length;
    if (tutors > lastTutorCount.current) {
      setChatOpen(true);
    }
    lastTutorCount.current = tutors;
  }, [view]);

  const send = useCallback(
    async (kind: "logic" | "chat" | "code", text: string) => {
      if (!text.trim()) return;
      begin(kind);
      try {
        setView(await api.event(PROBLEM_ID, kind, text));
      } catch (e) {
        fail(e);
      } finally {
        setBusy(null);
      }
    },
    [],
  );

  const onReset = useCallback(async () => {
    begin("reset");
    try {
      await api.reset(PROBLEM_ID);
      const v = await api.start(PROBLEM_ID);
      setView(v);
      lastTutorCount.current = 0;
      setChatOpen(false);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }, []);

  const isBusy = busy !== null;
  const done = view?.phase === "DONE";

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Header view={view} busy={isBusy} onReset={onReset} />

      {error && (
        <div className="shrink-0 border-b border-[var(--fail)] bg-[#2a1416] px-5 py-2 text-xs text-[var(--fail)]">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 underline opacity-70 hover:opacity-100"
          >
            dismiss
          </button>
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <ProblemPane problem={problem} view={view} />

        <section className="relative flex min-h-0 flex-col bg-[var(--background)]">
          {isBusy && <BusyBar label={BUSY_LABEL[busy]} since={busySince} />}

          <WorkPane
            view={view}
            starterCode={problem?.starter_code ?? ""}
            busy={isBusy}
            onSubmitLogic={(t) => send("logic", t)}
            onSubmitCode={(t) => send("code", t)}
          />

          <TestDrawer execution={view?.last_execution ?? null} />

          <ChatPanel
            messages={view?.messages ?? []}
            open={chatOpen}
            onOpenChange={setChatOpen}
            onSend={(t) => send("chat", t)}
            busy={busy === "chat"}
            disabled={isBusy || done}
            done={done}
          />
        </section>
      </main>

      <UnderTheHood view={view} />
    </div>
  );
}
