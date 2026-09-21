package com.logistream.domain.repo;

import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.logistream.domain.model.Models.ProblemRow;
import com.logistream.domain.model.Models.TestRow;

/**
 * JdbcTemplate, not JPA: CLAUDE.md section 3 swaps Spring Data out precisely to
 * avoid jsonb mapping pain. jsonb columns come back as text and are parsed with
 * Jackson here, so the rest of the service works with JsonNode.
 */
@Repository
public class ProblemRepository {

    private final JdbcTemplate jdbc;
    private final RowMapper<ProblemRow> problemMapper;

    public ProblemRepository(JdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.problemMapper = (rs, n) -> {
            try {
                return new ProblemRow(
                        rs.getString("id"),
                        rs.getString("title"),
                        rs.getString("description"),
                        mapper.readTree(rs.getString("examples")),
                        rs.getString("starter_code"),
                        rs.getString("harness_python"),
                        mapper.readTree(rs.getString("rubric")),
                        rs.getInt("rubric_version"),
                        rs.getBigDecimal("cpu_time_limit"),
                        rs.getBigDecimal("wall_time_limit"),
                        rs.getInt("memory_limit_kb"));
            } catch (Exception e) {
                throw new IllegalStateException(
                        "problem " + rs.getString("id") + " has unparseable jsonb", e);
            }
        };
    }

    private static final RowMapper<TestRow> TEST_MAPPER = (rs, n) -> new TestRow(
            rs.getInt("idx"),
            rs.getString("label"),
            rs.getBoolean("is_public"),
            rs.getString("stdin"),
            rs.getString("expected_output"));

    public Optional<ProblemRow> findProblem(String id) {
        List<ProblemRow> rows = jdbc.query("""
                SELECT id, title, description, examples, starter_code, harness_python,
                       rubric, rubric_version, cpu_time_limit, wall_time_limit, memory_limit_kb
                  FROM app.problems
                 WHERE id = ?
                """, problemMapper, id);
        return rows.stream().findFirst();
    }

    /** All tests for a problem, in index order. Hidden ones included. */
    public List<TestRow> findTests(String problemId) {
        return jdbc.query("""
                SELECT idx, label, is_public, stdin, expected_output
                  FROM app.hidden_tests
                 WHERE problem_id = ?
                 ORDER BY idx
                """, TEST_MAPPER, problemId);
    }
}
