package com.pil.ies.domain;

import jakarta.persistence.*;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "audit_events", indexes = @Index(name = "idx_audit_job_created", columnList = "job_id,created_at"))
public class AuditEvent {
    @Id
    private UUID id;
    @Column(name = "job_id", nullable = false)
    private UUID jobId;
    @Column(nullable = false, length = 80)
    private String action;
    @Column(nullable = false, length = 120)
    private String actor;
    @Column(length = 1000)
    private String detail;
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    protected AuditEvent() {}

    public AuditEvent(UUID jobId, String action, String actor, String detail) {
        this.id = UUID.randomUUID();
        this.jobId = jobId;
        this.action = action;
        this.actor = actor;
        this.detail = detail;
        this.createdAt = Instant.now();
    }

    public UUID getId() { return id; }
    public UUID getJobId() { return jobId; }
    public String getAction() { return action; }
    public String getActor() { return actor; }
    public String getDetail() { return detail; }
    public Instant getCreatedAt() { return createdAt; }
}
