package com.logistream.domain.config;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Guards {@code /internal/**}: no valid {@code X-Internal-Token}, no entry.
 *
 * <p>These endpoints hand out the rubric and the hidden tests, so this is the
 * line between what a student's browser may see and what only Python may see
 * (CLAUDE.md section 5.4). Registered explicitly with a URL pattern so it never
 * runs for the public routes.
 */
@Configuration
public class InternalTokenFilterConfig {

    private static final Logger log = LoggerFactory.getLogger(InternalTokenFilterConfig.class);

    public static final String HEADER = "X-Internal-Token";

    @Bean
    public FilterRegistrationBean<InternalTokenGuard> internalTokenFilterRegistration(
            @Value("${logistream.internal-token}") String expectedToken) {

        FilterRegistrationBean<InternalTokenGuard> reg = new FilterRegistrationBean<>();
        reg.setFilter(new InternalTokenGuard(expectedToken));
        reg.addUrlPatterns("/internal/*");
        reg.setOrder(Ordered.HIGHEST_PRECEDENCE + 10);   // after TraceIdFilter
        return reg;
    }

    static class InternalTokenGuard extends OncePerRequestFilter {

        private final byte[] expected;

        InternalTokenGuard(String expectedToken) {
            this.expected = expectedToken.getBytes(StandardCharsets.UTF_8);
        }

        @Override
        protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                        FilterChain chain) throws ServletException, IOException {
            String presented = request.getHeader(HEADER);

            if (presented == null
                    || !MessageDigest.isEqual(presented.getBytes(StandardCharsets.UTF_8), expected)) {
                log.warn("rejected {} {} - {} {}", request.getMethod(), request.getRequestURI(),
                        HEADER, presented == null ? "missing" : "invalid");
                response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
                response.setContentType("application/json");
                response.getWriter().write("{\"error\":\"missing or invalid " + HEADER + "\"}");
                return;
            }

            chain.doFilter(request, response);
        }
    }
}
