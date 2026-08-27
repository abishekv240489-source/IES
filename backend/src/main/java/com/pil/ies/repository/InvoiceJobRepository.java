package com.pil.ies.repository;

import com.pil.ies.domain.InvoiceJob;
import com.pil.ies.domain.JobStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.Optional;
import java.util.UUID;

public interface InvoiceJobRepository extends JpaRepository<InvoiceJob, UUID> {
    Optional<InvoiceJob> findFirstBySha256AndStatusIn(String sha256, Collection<JobStatus> statuses);
    Page<InvoiceJob> findByStatus(JobStatus status, Pageable pageable);
    long countByStatus(JobStatus status);
}
