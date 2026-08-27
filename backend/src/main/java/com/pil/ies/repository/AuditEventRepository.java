package com.pil.ies.repository;

import com.pil.ies.domain.AuditEvent;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface AuditEventRepository extends JpaRepository<AuditEvent, UUID> {
    List<AuditEvent> findByJobIdOrderByCreatedAtAsc(UUID jobId);
}
