package com.logistream.domain.config;

import java.net.URI;
import javax.sql.DataSource;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

/**
 * Builds the DataSource from the shared {@code DATABASE_URL} env var.
 *
 * <p>CLAUDE.md keeps one {@code DATABASE_URL} across all services so that
 * swapping local Postgres for Supabase later is a config change and nothing
 * else. That value is a libpq URL
 * ({@code postgresql://user:pass@host:port/db}), which JDBC cannot consume
 * directly, so it is translated here rather than duplicated in the env file.
 *
 * <p>If {@code DATABASE_URL} is absent we fall back to the
 * {@code spring.datasource.*} defaults in application.yml.
 */
@Configuration
public class DataSourceConfig {

    private static final Logger log = LoggerFactory.getLogger(DataSourceConfig.class);

    @Bean
    public DataSource dataSource(Environment env) {
        String databaseUrl = env.getProperty("DATABASE_URL");

        if (databaseUrl == null || databaseUrl.isBlank()) {
            String url = env.getProperty("spring.datasource.url");
            log.info("DATABASE_URL not set, using spring.datasource.url={}", url);
            return DataSourceBuilder.create()
                    .url(url)
                    .username(env.getProperty("spring.datasource.username"))
                    .password(env.getProperty("spring.datasource.password"))
                    .build();
        }

        URI uri = URI.create(databaseUrl);
        String user = null;
        String password = null;
        String userInfo = uri.getUserInfo();
        if (userInfo != null) {
            int sep = userInfo.indexOf(':');
            user = sep >= 0 ? userInfo.substring(0, sep) : userInfo;
            password = sep >= 0 ? userInfo.substring(sep + 1) : null;
        }

        int port = uri.getPort() > 0 ? uri.getPort() : 5432;
        String jdbcUrl = "jdbc:postgresql://" + uri.getHost() + ":" + port + uri.getPath();

        // never log the password
        log.info("DataSource from DATABASE_URL: {} (user={})", jdbcUrl, user);

        return DataSourceBuilder.create()
                .url(jdbcUrl)
                .username(user)
                .password(password)
                .build();
    }
}
