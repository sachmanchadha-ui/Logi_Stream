package com.logistream.domain.exec;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.List;

/**
 * Where student code actually runs.
 *
 * <p>Two implementations exist. {@link LocalPythonSandbox} is the default and
 * runs the code in a subprocess on this host; {@link com.logistream.domain.judge0.Judge0Client}
 * talks to the hosted Judge0 CE API. Selected by {@code EXECUTOR_MODE}.
 *
 * <p>The seam is worth the ten lines: CLAUDE.md section 3 promised that moving
 * between sandboxes would touch only the execution layer, and it does. Both
 * implementations speak Judge0's status ids, so {@link BucketMapper} and the
 * whole section 8 table are identical either way.
 */
public interface Sandbox {

    /** Human-readable mode name, logged at startup and reported by /health. */
    String name();

    /** True when this sandbox has everything it needs to run. */
    boolean available();

    /** Runs every submission and returns their results in the same order. */
    BatchOutcome runBatch(List<Submission> submissions) throws IOException, InterruptedException;

    /** One submission as we send it. */
    record Submission(
            String sourceCode,
            String stdin,
            BigDecimal cpuTimeLimit,
            BigDecimal wallTimeLimit,
            int memoryLimitKb) {
    }

    /**
     * One submission's outcome, using Judge0's status ids so that the bucket
     * mapping is sandbox-independent:
     *
     * <ul>
     *   <li>3  - finished normally (stdout still has to match)</li>
     *   <li>5  - time limit exceeded</li>
     *   <li>11 - non-zero exit / NZEC, including python SyntaxError (section 8, trap 2)</li>
     *   <li>13 - internal error, i.e. the sandbox itself failed</li>
     * </ul>
     */
    record Result(
            String token,
            int statusId,
            String statusDescription,
            String stdout,
            String stderr,
            String compileOutput,
            String time) {

        public boolean pending() {
            return statusId == 1 || statusId == 2;
        }

        /** stderr and compile_output together -- callers almost always want both. */
        public String combinedError() {
            String a = stderr == null ? "" : stderr;
            String b = compileOutput == null ? "" : compileOutput;
            return (a + (a.isEmpty() || b.isEmpty() ? "" : "\n") + b).trim();
        }
    }

    /**
     * What one batch cost and produced.
     *
     * @param requestsUsed billed upstream requests; always 0 for local execution
     * @param timedOut     true if work was still queued when the poll budget ran out
     */
    record BatchOutcome(List<Result> results, int requestsUsed, boolean timedOut) {
    }
}
