package com.logistream.domain.web;

import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.logistream.domain.exec.ExecutionService;
import com.logistream.domain.model.Models.ExecuteRequest;
import com.logistream.domain.model.Models.ProblemContext;
import com.logistream.domain.model.Models.ProblemRow;
import com.logistream.domain.repo.ProblemRepository;

/**
 * Internal endpoints -- Python only. Everything under /internal/** is behind
 * InternalTokenFilter, and everything here may contain the rubric, hidden test
 * inputs and expected outputs.
 */
@RestController
@RequestMapping("/internal")
public class InternalController {

    private static final Logger log = LoggerFactory.getLogger(InternalController.class);

    private final ProblemRepository repo;
    private final ExecutionService executor;

    public InternalController(ProblemRepository repo, ExecutionService executor) {
        this.repo = repo;
        this.executor = executor;
    }

    @GetMapping("/problems/{id}/context")
    public ResponseEntity<?> context(@PathVariable String id) {
        return repo.findProblem(id)
                .<ResponseEntity<?>>map(p -> ResponseEntity.ok(new ProblemContext(
                        p.id(), p.title(), p.description(), p.rubric(),
                        p.rubricVersion(), p.starterCode())))
                .orElseGet(() -> ResponseEntity.status(404)
                        .body(Map.of("error", "unknown problem: " + id)));
    }

    @PostMapping("/execute")
    public ResponseEntity<?> execute(@RequestBody ExecuteRequest req) {
        if (req.problem_id() == null || req.problem_id().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "problem_id is required"));
        }
        if (req.source() == null || req.source().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "source is required"));
        }
        // MVP is python-only; language is already a field so adding more is config, not surgery
        String language = req.language() == null ? "python" : req.language();
        if (!"python".equalsIgnoreCase(language)) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "unsupported language: " + language));
        }

        ProblemRow problem = repo.findProblem(req.problem_id()).orElse(null);
        if (problem == null) {
            return ResponseEntity.status(404)
                    .body(Map.of("error", "unknown problem: " + req.problem_id()));
        }

        log.info("execute request problem={} source_bytes={}", problem.id(), req.source().length());
        return ResponseEntity.ok(executor.execute(problem, req.source()));
    }
}
