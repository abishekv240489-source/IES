package com.pil.ies.domain;

import jakarta.persistence.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "invoice_jobs", indexes = {
        @Index(name = "idx_invoice_jobs_created_at", columnList = "created_at"),
        @Index(name = "idx_invoice_jobs_status", columnList = "status"),
        @Index(name = "idx_invoice_jobs_sha256", columnList = "sha256")
})
public class InvoiceJob {
    @Id
    private UUID id;
    @Column(name = "batch_id", nullable = false)
    private UUID batchId;
    @Column(name = "original_filename", nullable = false, length = 255)
    private String originalFilename;
    @Column(name = "stored_filename", nullable = false, length = 255)
    private String storedFilename;
    @Column(nullable = false, length = 64)
    private String sha256;
    @Column(name = "content_type", nullable = false, length = 100)
    private String contentType;
    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;
    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 40)
    private JobStatus status;
    @Column(name = "overall_confidence")
    private Double overallConfidence;
    @Column(name = "extraction_engine", length = 80)
    private String extractionEngine;
    @Column(name = "extraction_json", columnDefinition = "text")
    private String extractionJson;
    @Column(name = "validation_json", columnDefinition = "text")
    private String validationJson;
    @Column(name = "error_message", length = 1000)
    private String errorMessage;
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
    @Column(name = "started_at")
    private Instant startedAt;
    @Column(name = "completed_at")
    private Instant completedAt;
    @Version
    private long version;

    protected InvoiceJob() {}

    public static InvoiceJob queued(UUID batchId, String originalFilename, String storedFilename,
                                    String sha256, String contentType, long sizeBytes) {
        var job = new InvoiceJob();
        job.id = UUID.randomUUID();
        job.batchId = batchId;
        job.originalFilename = originalFilename;
        job.storedFilename = storedFilename;
        job.sha256 = sha256;
        job.contentType = contentType;
        job.sizeBytes = sizeBytes;
        job.status = JobStatus.QUEUED;
        job.createdAt = Instant.now();
        job.updatedAt = job.createdAt;
        return job;
    }

    public void transition(JobStatus next) {
        status = next;
        updatedAt = Instant.now();
        if (startedAt == null && next != JobStatus.QUEUED) startedAt = updatedAt;
        if (next == JobStatus.COMPLETED || next == JobStatus.PENDING_REVIEW || next == JobStatus.FAILED || next == JobStatus.REJECTED) {
            completedAt = updatedAt;
        }
    }

    public void complete(String extractionJson, String validationJson, double confidence, String engine, boolean reviewRequired) {
        this.extractionJson = extractionJson;
        this.validationJson = validationJson;
        this.overallConfidence = confidence;
        this.extractionEngine = engine;
        transition(reviewRequired ? JobStatus.PENDING_REVIEW : JobStatus.COMPLETED);
    }

    public void fail(String message) {
        errorMessage = message == null ? "Processing failed" : message.substring(0, Math.min(message.length(), 1000));
        transition(JobStatus.FAILED);
    }

    public void applyReview(String extractionJson, String validationJson, boolean approved) {
        this.extractionJson = extractionJson;
        this.validationJson = validationJson;
        transition(approved ? JobStatus.COMPLETED : JobStatus.REJECTED);
    }

    public UUID getId() { return id; }
    public UUID getBatchId() { return batchId; }
    public String getOriginalFilename() { return originalFilename; }
    public String getStoredFilename() { return storedFilename; }
    public String getSha256() { return sha256; }
    public String getContentType() { return contentType; }
    public long getSizeBytes() { return sizeBytes; }
    public JobStatus getStatus() { return status; }
    public Double getOverallConfidence() { return overallConfidence; }
    public String getExtractionEngine() { return extractionEngine; }
    public String getExtractionJson() { return extractionJson; }
    public String getValidationJson() { return validationJson; }
    public String getErrorMessage() { return errorMessage; }
    public Instant getCreatedAt() { return createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public Instant getStartedAt() { return startedAt; }
    public Instant getCompletedAt() { return completedAt; }
}
