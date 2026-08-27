package com.pil.ies.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.nio.file.Path;
import java.util.List;

@ConfigurationProperties(prefix = "ies")
public record IesProperties(
        Path storageRoot,
        long maxFileBytes,
        int maxPages,
        String aiWorkerUrl,
        boolean aiDemoFallback,
        double minFieldConfidence,
        List<String> allowedOrigins
) {
}
