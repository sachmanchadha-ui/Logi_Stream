package com.logistream.domain.config;

import java.io.IOException;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Puts the inbound {@code X-Trace-Id} into the MDC so every log line in this
 * service carries it (CLAUDE.md section 1.7). The gateway generates the id and
 * forwards it; if a request arrives without one we mint a local id rather than
 * logging {@code none}, so an orphan request is still traceable.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(TraceIdFilter.class);

    public static final String HEADER = "X-Trace-Id";
    public static final String MDC_KEY = "traceId";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String traceId = request.getHeader(HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = "local-" + UUID.randomUUID();
        }
        MDC.put(MDC_KEY, traceId);
        response.setHeader(HEADER, traceId);
        long startedAt = System.nanoTime();
        try {
            chain.doFilter(request, response);
        } finally {
            // CLAUDE.md section 1.7 asks every service to log the trace id on EVERY
            // request. Putting it in the MDC is not enough on its own: a request
            // that succeeds without logging anything leaves no line to correlate,
            // so a successful GET /problems/{id} was invisible in the trace.
            long ms = (System.nanoTime() - startedAt) / 1_000_000;
            log.info("{} {} -> {} ({} ms)",
                    request.getMethod(), request.getRequestURI(), response.getStatus(), ms);
            MDC.remove(MDC_KEY);
        }
    }
}
