package com.logistream.domain.web;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import com.logistream.domain.model.Models.ProblemView;
import com.logistream.domain.repo.ProblemRepository;

/** Public endpoints. Whatever leaves here may reach the browser. */
@RestController
public class ProblemController {

    private final ProblemRepository repo;

    public ProblemController(ProblemRepository repo) {
        this.repo = repo;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("ok", true);
    }

    /**
     * GET /problems/{id}
     *
     * <p>Builds a ProblemView field by field rather than returning the row, so
     * the rubric and the hidden tests cannot leak by accident. That is the whole
     * point of this endpoint existing separately from the internal one.
     */
    @GetMapping("/problems/{id}")
    public ResponseEntity<?> problem(@PathVariable String id) {
        return repo.findProblem(id)
                .<ResponseEntity<?>>map(p -> ResponseEntity.ok(new ProblemView(
                        p.id(), p.title(), p.description(), p.examples(),
                        p.starterCode(), "python")))
                .orElseGet(() -> ResponseEntity.status(404)
                        .body(Map.of("error", "unknown problem: " + id)));
    }
}
