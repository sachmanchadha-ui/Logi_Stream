-- LogiStream schema (CLAUDE.md §7.1)
CREATE SCHEMA IF NOT EXISTS app;   -- owned by Java
CREATE SCHEMA IF NOT EXISTS orch;  -- owned by Python (LangGraph tables go in public via setup())

CREATE TABLE app.users (id TEXT PRIMARY KEY, display_name TEXT NOT NULL);

CREATE TABLE app.problems (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,          -- markdown
  examples JSONB NOT NULL,
  starter_code TEXT NOT NULL,
  harness_python TEXT NOT NULL,       -- appended after student code by Java
  rubric JSONB NOT NULL,
  rubric_version INT NOT NULL DEFAULT 1,
  cpu_time_limit NUMERIC NOT NULL DEFAULT 2,
  wall_time_limit NUMERIC NOT NULL DEFAULT 5,
  memory_limit_kb INT NOT NULL DEFAULT 128000
);

CREATE TABLE app.hidden_tests (
  problem_id TEXT REFERENCES app.problems(id),
  idx INT NOT NULL,
  label TEXT NOT NULL,
  is_public BOOLEAN NOT NULL DEFAULT FALSE,
  stdin TEXT NOT NULL,
  expected_output TEXT NOT NULL,
  PRIMARY KEY (problem_id, idx)
);

CREATE TABLE orch.verdict_cache (
  cache_key TEXT PRIMARY KEY,
  problem_id TEXT NOT NULL,
  verdict JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
