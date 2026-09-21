// Mirrors the SessionView contract (CLAUDE.md section 5.2).
//
// The gateway passes this through from Python unchanged, so these types are the
// contract. Note what is deliberately absent from LastEval: the evaluator's
// free-text `rationale` is logged server-side and never sent here.

export type Phase = "LOGIC" | "CODE" | "DONE";

export type Status =
  | "LOGIC_WRITE"
  | "LOGIC_CHAT"
  | "CODE_WRITE"
  | "CODE_CHAT"
  | "SUCCESS";

export type Bucket =
  | "ACCEPTED"
  | "WRONG_ANSWER"
  | "TLE"
  | "COMPILE_ERROR"
  | "RUNTIME_ERROR"
  | "INFRA_ERROR";

export interface Message {
  role: "student" | "tutor" | "system";
  kind: "logic" | "chat" | "code" | "hint" | "result" | "info";
  text: string;
  ts: string;
}

export interface LastEval {
  verdict: "PASS" | "FAIL" | "FLAGGED";
  matched_approach: string | null;
  missing_steps: string[];
  violated_invariants: string[];
  misconception_id: string | null;
  confidence: number;
  cache_hit: boolean;
}

export interface TestResult {
  index: number;
  label: string;
  is_public: boolean;
  passed: boolean;
  status: string | null;
  time: string | null;
  stderr_excerpt: string;
  // present only when is_public - hidden tests are stripped server-side
  stdin?: string;
  expected?: string;
  stdout?: string;
}

export interface LastExecution {
  bucket: Bucket;
  passed: number;
  total: number;
  tests: TestResult[];
}

export interface DebugInfo {
  trace_id: string | null;
  last_node_path: string[];
  regenerations: number;
  verifier_rejections: { reason: string }[];
  fallback_used: boolean;
}

export interface SessionView {
  thread_id: string;
  problem_id: string;
  phase: Phase;
  status: Status;
  attempts: { logic: number; code: number };
  accepted_logic: string | null;
  messages: Message[];
  last_eval: LastEval | null;
  last_execution: LastExecution | null;
  debug: DebugInfo;
}

export interface ProblemExample {
  input: string;
  output: string;
  explanation: string;
}

export interface Problem {
  id: string;
  title: string;
  description: string;
  examples: ProblemExample[];
  starter_code: string;
  language: string;
}
