package com.pil.ies.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.pil.ies.domain.AuditEvent;
import com.pil.ies.domain.InvoiceJob;
import com.pil.ies.domain.JobStatus;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class ApiModels {
    private ApiModels() {}

    public record UploadItem(UUID id, String filename, JobStatus status, boolean duplicate, String message) {}
    public record UploadResponse(UUID batchId, List<UploadItem> jobs) {}
    public record ReviewRequest(JsonNode extraction, boolean approved, String remarks) {}
    public record JobResponse(UUID id, UUID batchId, String filename, JobStatus status, long sizeBytes,
                              Double confidence, String engine, JsonNode extraction, JsonNode validation,
                              String error, Instant createdAt, Instant updatedAt, Long latencyMs) {
        public static JobResponse from(InvoiceJob job, JsonNode extraction, JsonNode validation) {
            Long latency = job.getStartedAt() != null && job.getCompletedAt() != null
                    ? Duration.between(job.getStartedAt(), job.getCompletedAt()).toMillis() : null;
            return new JobResponse(job.getId(), job.getBatchId(), job.getOriginalFilename(), job.getStatus(),
                    job.getSizeBytes(), job.getOverallConfidence(), job.getExtractionEngine(), extraction,
                    validation, job.getErrorMessage(), job.getCreatedAt(), job.getUpdatedAt(), latency);
        }
    }
    public record AuditResponse(UUID id, String action, String actor, String detail, Instant createdAt) {
        public static AuditResponse from(AuditEvent event) {
            return new AuditResponse(event.getId(), event.getAction(), event.getActor(), event.getDetail(), event.getCreatedAt());
        }
    }
    public record DashboardResponse(long total, long queued, long processing, long pendingReview,
                                    long completed, long failed, Map<String, Object> targets) {}
}
