package com.logistream.domain.judge0;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "logistream.judge0")
public class Judge0Properties {

    private String url = "https://judge0-ce.p.rapidapi.com";
    private String rapidapiKey = "";
    private String rapidapiHost = "judge0-ce.p.rapidapi.com";
    private int pythonLanguageId = 71;
    private long pollIntervalMs = 1000;
    private int maxPolls = 15;

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public String getRapidapiKey() {
        return rapidapiKey;
    }

    public void setRapidapiKey(String rapidapiKey) {
        this.rapidapiKey = rapidapiKey;
    }

    public String getRapidapiHost() {
        return rapidapiHost;
    }

    public void setRapidapiHost(String rapidapiHost) {
        this.rapidapiHost = rapidapiHost;
    }

    public int getPythonLanguageId() {
        return pythonLanguageId;
    }

    public void setPythonLanguageId(int pythonLanguageId) {
        this.pythonLanguageId = pythonLanguageId;
    }

    public long getPollIntervalMs() {
        return pollIntervalMs;
    }

    public void setPollIntervalMs(long pollIntervalMs) {
        this.pollIntervalMs = pollIntervalMs;
    }

    public int getMaxPolls() {
        return maxPolls;
    }

    public void setMaxPolls(int maxPolls) {
        this.maxPolls = maxPolls;
    }
}
