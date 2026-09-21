package com.logistream.domain.model;

import java.math.BigDecimal;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.JsonNode;

/**
 * Wire and row types for the domain service (CLAUDE.md section 5.4).
 *
 * <p>Kept in one file on purpose: they are all small, they only exist to pin
 * down the contract, and one file is easier to diff against section 5.4 than
 * a dozen.
 */
public final class Models {

    private Models() {
    }

    // ---------------------------------------------------------------- rows

    /** One row of app.problems. Not returned to anyone as-is. */
    public record ProblemRow(
            String id,
            String title,
            String description,
            JsonNode examples,
            String starterCode,
            String harnessPython,
            JsonNode rubric,
            int rubricVersion,
            BigDecimal cpuTimeLimit,
            BigDecimal wallTimeLimit,
            int memoryLimitKb) {
    }

    /** One row of app.hidden_tests. */
    public record TestRow(
            int idx,
            String label,
            boolean isPublic,
            String stdin,
            String expectedOutput) {
    }

    // ------------------------------------------------------------ public API

    /**
     * GET /problems/{id}. Deliberately has no rubric and no tests: this is the
     * only problem payload the browser ever sees.
     */
    public record ProblemView(
            String id,
            String title,
            String description,
            JsonNode examples,
            String starter_code,
            String language) {
    }

    // ----------------------------------------------------------- internal API

    /** GET /internal/problems/{id}/context. Python only. */
    public record ProblemContext(
            String id,
            String title,
            String description,
            JsonNode rubric,
            int rubric_version,
            String starter_code) {
    }

    /** POST /internal/execute request. */
    public record ExecuteRequest(
            String problem_id,
            String language,
            String source) {
    }

    /**
     * One test's outcome. Java returns full detail including hidden stdin and
     * expected output; Python strips those before anything reaches SessionView.
     */
    @JsonInclude(JsonInclude.Include.ALWAYS)
    public record TestResult(
            int index,
            String label,
            boolean is_public,
            Integer status_id,
            String status_description,
            boolean passed,
            String time,
            String stdin,
            String expected,
            String stdout,
            String stderr) {
    }

    /** POST /internal/execute response. */
    public record ExecuteResponse(
            String bucket,
            int passed,
            int total,
            boolean infra_retry_used,
            List<TestResult> tests) {
    }
}
