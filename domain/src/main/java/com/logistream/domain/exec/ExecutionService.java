package com.logistream.domain.exec;

import java.util.ArrayList;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.logistream.domain.exec.BucketMapper.Scored;
import com.logistream.domain.judge0.Judge0Client;
import com.logistream.domain.judge0.Judge0Client.BatchOutcome;
import com.logistream.domain.judge0.Judge0Client.Result;
import com.logistream.domain.judge0.Judge0Client.Submission;
import com.logistream.domain.model.Models.ExecuteResponse;
import com.logistream.domain.model.Models.ProblemRow;
import com.logistream.domain.model.Models.TestResult;
import com.logistream.domain.model.Models.TestRow;
import com.logistream.domain.repo.ProblemRepository;

/**
 * Runs a student's code against every test for a problem.
 *
 * <p>One batch, one bucket. The only retry in the system lives here: if the
 * first batch comes back with a Judge0 internal error (status 13/14) the whole
 * batch is submitted once more, and that is the end of it. Anything more would
 * quietly eat the hosted quota (CLAUDE.md trap 1).
 */
@Service
public class ExecutionService {

    private static final Logger log = LoggerFactory.getLogger(ExecutionService.class);

    private final ProblemRepository repo;
    private final Judge0Client judge0;

    public ExecutionService(ProblemRepository repo, Judge0Client judge0) {
        this.repo = repo;
        this.judge0 = judge0;
    }

    public ExecuteResponse execute(ProblemRow problem, String studentSource) {
        List<TestRow> tests = repo.findTests(problem.id());
        if (tests.isEmpty()) {
            throw new IllegalStateException("problem " + problem.id() + " has no tests");
        }

        // the harness is appended after the student's code, exactly as section 8 says
        String source = studentSource + "\n\n" + problem.harnessPython();

        List<Submission> submissions = tests.stream()
                .map(t -> new Submission(source, t.stdin(),
                        problem.cpuTimeLimit(), problem.wallTimeLimit(), problem.memoryLimitKb()))
                .toList();

        int totalRequests = 0;
        boolean infraRetryUsed = false;

        BatchOutcome outcome;
        try {
            outcome = judge0.runBatch(submissions);
            totalRequests += outcome.requestsUsed();

            if (needsInfraRetry(outcome)) {
                log.warn("judge0 returned an internal error (13/14) - retrying the batch once");
                infraRetryUsed = true;
                outcome = judge0.runBatch(submissions);
                totalRequests += outcome.requestsUsed();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return infraError(tests, totalRequests, infraRetryUsed, "interrupted");
        } catch (Exception e) {
            log.error("judge0 call failed: {}", e.toString());
            return infraError(tests, totalRequests, infraRetryUsed, e.toString());
        }

        List<Result> results = outcome.results();
        if (results.size() != tests.size()) {
            log.error("judge0 returned {} results for {} tests", results.size(), tests.size());
            return infraError(tests, totalRequests, infraRetryUsed, "result count mismatch");
        }

        List<Scored> scored = new ArrayList<>();
        List<TestResult> testResults = new ArrayList<>();

        for (int i = 0; i < tests.size(); i++) {
            TestRow t = tests.get(i);
            Result r = results.get(i);

            boolean matched = r.statusId() == 3
                    && BucketMapper.outputMatches(r.stdout(), t.expectedOutput());
            scored.add(new Scored(r, matched));

            testResults.add(new TestResult(
                    t.idx(), t.label(), t.isPublic(),
                    r.statusId(), r.statusDescription(),
                    matched,
                    r.time(),
                    t.stdin(), t.expectedOutput(), r.stdout(), r.combinedError()));
        }

        String bucket = BucketMapper.bucketOf(scored, outcome.timedOut());
        int passed = (int) testResults.stream().filter(TestResult::passed).count();

        log.info("execute problem={} bucket={} passed={}/{} judge0_requests={} infra_retry={}",
                problem.id(), bucket, passed, tests.size(), totalRequests, infraRetryUsed);

        return new ExecuteResponse(bucket, passed, tests.size(), infraRetryUsed, testResults);
    }

    private static boolean needsInfraRetry(BatchOutcome outcome) {
        return outcome.results().stream().anyMatch(r -> r.statusId() == 13 || r.statusId() == 14);
    }

    /** A sandbox failure is not the student's fault; the attempt must not count. */
    private ExecuteResponse infraError(List<TestRow> tests, int requests, boolean retryUsed, String why) {
        log.warn("execute -> INFRA_ERROR ({}), judge0_requests={}", why, requests);
        List<TestResult> results = tests.stream()
                .map(t -> new TestResult(t.idx(), t.label(), t.isPublic(),
                        null, "Infrastructure error", false, null,
                        t.stdin(), t.expectedOutput(), "", why))
                .toList();
        return new ExecuteResponse(BucketMapper.INFRA_ERROR, 0, tests.size(), retryUsed, results);
    }
}
