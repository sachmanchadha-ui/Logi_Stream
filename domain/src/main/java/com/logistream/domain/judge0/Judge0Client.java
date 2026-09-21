package com.logistream.domain.judge0;

import java.io.IOException;
import java.math.BigDecimal;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.logistream.domain.exec.Sandbox;

/**
 * Hosted Judge0 CE client (CLAUDE.md section 8, judge0/HOSTED.md).
 *
 * <p>Two calls only: one batch submit, then batch polls. base64 in both
 * directions. {@code expected_output} is never sent -- Java compares stdout
 * itself, so we never inherit Judge0's whitespace semantics.
 *
 * <p>Quota is finite and <em>every submit and every poll is billed</em>, so this
 * class counts its requests and the count is returned with the results. There
 * are no retries in here at all; the single infra retry lives one level up in
 * ExecutionService, where it is visible.
 */
@Component
@ConditionalOnProperty(name = "logistream.executor.mode", havingValue = "JUDGE0")
public class Judge0Client implements Sandbox {

    private static final Logger log = LoggerFactory.getLogger(Judge0Client.class);

    /** Judge0 statuses that mean "not finished yet". */
    public static final int STATUS_IN_QUEUE = 1;
    public static final int STATUS_PROCESSING = 2;

    private static final String POLL_FIELDS =
            "token,status_id,status,stdout,stderr,compile_output,time,memory";

    private final Judge0Properties props;
    private final ObjectMapper mapper;
    private final HttpClient http;

    public Judge0Client(Judge0Properties props, ObjectMapper mapper) {
        this.props = props;
        this.mapper = mapper;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(20))
                .build();
    }

    @Override
    public String name() {
        return "JUDGE0_HOSTED(" + props.getUrl() + ")";
    }

    @Override
    public boolean available() {
        return configured();
    }

    public boolean configured() {
        return props.getRapidapiKey() != null && !props.getRapidapiKey().isBlank();
    }

    /**
     * Submits the whole batch and polls until every submission has left status
     * 1/2, or until maxPolls is reached.
     *
     * @return the results plus the number of Judge0 requests consumed
     */
    @Override
    public BatchOutcome runBatch(List<Submission> submissions) throws IOException, InterruptedException {
        AtomicInteger requests = new AtomicInteger();

        List<String> tokens = submit(submissions, requests);
        log.info("judge0 submitted batch of {} -> {} token(s)", submissions.size(), tokens.size());

        List<Result> results = List.of();
        boolean timedOut = true;

        for (int poll = 1; poll <= props.getMaxPolls(); poll++) {
            Thread.sleep(props.getPollIntervalMs());
            results = poll(tokens, requests);

            long stillPending = results.stream().filter(Result::pending).count();
            if (stillPending == 0) {
                log.info("judge0 batch finished on poll {} ({} requests used)", poll, requests.get());
                timedOut = false;
                break;
            }
            log.debug("judge0 poll {}: {}/{} still pending", poll, stillPending, results.size());
        }

        if (timedOut) {
            log.warn("judge0 batch still pending after {} polls -> INFRA_ERROR ({} requests used)",
                    props.getMaxPolls(), requests.get());
        }

        return new BatchOutcome(results, requests.get(), timedOut);
    }

    // ------------------------------------------------------------------ calls

    private List<String> submit(List<Submission> submissions, AtomicInteger requests)
            throws IOException, InterruptedException {

        ObjectNode body = mapper.createObjectNode();
        ArrayNode arr = body.putArray("submissions");
        for (Submission s : submissions) {
            ObjectNode n = arr.addObject();
            n.put("language_id", props.getPythonLanguageId());
            n.put("source_code", b64(s.sourceCode()));
            n.put("stdin", b64(s.stdin()));
            n.put("cpu_time_limit", s.cpuTimeLimit());
            n.put("wall_time_limit", s.wallTimeLimit());
            n.put("memory_limit", s.memoryLimitKb());
            // expected_output is deliberately absent: we compare stdout ourselves
        }

        HttpRequest req = request("/submissions/batch?base64_encoded=true")
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body),
                        StandardCharsets.UTF_8))
                .build();

        HttpResponse<String> res = send(req, requests);
        if (res.statusCode() / 100 != 2) {
            throw new IOException("judge0 submit failed: HTTP " + res.statusCode() + " " + excerpt(res.body()));
        }

        JsonNode parsed = mapper.readTree(res.body());
        if (!parsed.isArray()) {
            throw new IOException("judge0 submit returned no token array: " + excerpt(res.body()));
        }

        List<String> tokens = new ArrayList<>();
        for (JsonNode n : parsed) {
            JsonNode t = n.get("token");
            if (t == null || t.asText().isBlank()) {
                throw new IOException("judge0 submit returned a submission with no token: " + excerpt(res.body()));
            }
            tokens.add(t.asText());
        }
        if (tokens.size() != submissions.size()) {
            throw new IOException("judge0 returned " + tokens.size() + " tokens for "
                    + submissions.size() + " submissions");
        }
        return tokens;
    }

    private List<Result> poll(List<String> tokens, AtomicInteger requests)
            throws IOException, InterruptedException {

        String path = "/submissions/batch?tokens=" + String.join(",", tokens)
                + "&base64_encoded=true&fields=" + POLL_FIELDS;

        HttpResponse<String> res = send(request(path).GET().build(), requests);
        if (res.statusCode() / 100 != 2) {
            throw new IOException("judge0 poll failed: HTTP " + res.statusCode() + " " + excerpt(res.body()));
        }

        JsonNode parsed = mapper.readTree(res.body());
        JsonNode arr = parsed.isArray() ? parsed : parsed.get("submissions");
        if (arr == null || !arr.isArray()) {
            throw new IOException("judge0 poll returned no submissions: " + excerpt(res.body()));
        }

        List<Result> out = new ArrayList<>();
        for (JsonNode n : arr) {
            JsonNode status = n.get("status");
            int statusId = status != null && status.hasNonNull("id")
                    ? status.get("id").asInt()
                    : n.path("status_id").asInt(0);
            String desc = status != null ? status.path("description").asText("") : "";

            out.add(new Result(
                    n.path("token").asText(""),
                    statusId,
                    desc,
                    unb64(n.path("stdout")),
                    unb64(n.path("stderr")),
                    unb64(n.path("compile_output")),
                    n.path("time").asText(null)));
        }
        return out;
    }

    // ----------------------------------------------------------------- plumbing

    private HttpRequest.Builder request(String path) {
        HttpRequest.Builder b = HttpRequest.newBuilder()
                .uri(URI.create(props.getUrl() + path))
                .timeout(Duration.ofSeconds(60));
        // hosted mode: RapidAPI auth headers. A self-hosted instance needs neither.
        if (configured()) {
            b.header("X-RapidAPI-Key", props.getRapidapiKey());
            b.header("X-RapidAPI-Host", props.getRapidapiHost());
        }
        return b;
    }

    private HttpResponse<String> send(HttpRequest req, AtomicInteger requests)
            throws IOException, InterruptedException {
        int n = requests.incrementAndGet();
        log.debug("judge0 request #{} {} {}", n, req.method(), req.uri().getPath());
        return http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private static String b64(String s) {
        return Base64.getEncoder().encodeToString((s == null ? "" : s).getBytes(StandardCharsets.UTF_8));
    }

    /**
     * Decodes a base64 field. Judge0 returns null for empty streams, and very
     * occasionally plain text; neither should take a run down, so this degrades
     * instead of throwing.
     */
    private static String unb64(JsonNode node) {
        if (node == null || node.isNull() || node.isMissingNode()) {
            return "";
        }
        String raw = node.asText("");
        if (raw.isEmpty()) {
            return "";
        }
        try {
            return new String(Base64.getMimeDecoder().decode(raw), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            log.warn("judge0 field was not valid base64, using it verbatim");
            return raw;
        }
    }

    private static String excerpt(String body) {
        if (body == null) {
            return "(no body)";
        }
        return body.length() <= 300 ? body : body.substring(0, 300) + "...";
    }
}
