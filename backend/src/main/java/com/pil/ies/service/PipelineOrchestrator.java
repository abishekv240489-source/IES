package com.pil.ies.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.pil.ies.config.IesProperties;
import com.pil.ies.domain.AuditEvent;
import com.pil.ies.domain.JobStatus;
import com.pil.ies.repository.AuditEventRepository;
import com.pil.ies.repository.InvoiceJobRepository;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Path;
import java.util.UUID;

@Service
public class PipelineOrchestrator {
    private final InvoiceJobRepository jobs;
    private final AuditEventRepository audit;
    private final AiWorkerClient aiWorker;
    private final ValidationService validation;
    private final IesProperties properties;
    private final ObjectMapper mapper;

    public PipelineOrchestrator(InvoiceJobRepository jobs, AuditEventRepository audit, AiWorkerClient aiWorker,
                                ValidationService validation, IesProperties properties, ObjectMapper mapper) {
        this.jobs = jobs;
        this.audit = audit;
        this.aiWorker = aiWorker;
        this.validation = validation;
        this.properties = properties;
        this.mapper = mapper;
    }

    @Async
    @Transactional
    public void process(UUID jobId) {
        var job = jobs.findById(jobId).orElseThrow();
        try {
            job.transition(JobStatus.PREPROCESSING);
            audit.save(new AuditEvent(jobId, "PROCESSING_STARTED", "system", "Document entered the extraction pipeline"));
            Path file = properties.storageRoot().toAbsolutePath().normalize().resolve(job.getStoredFilename());
            job.transition(JobStatus.OCR_RUNNING);
            var result = aiWorker.extract(jobId, file, job.getOriginalFilename());
            job.transition(JobStatus.VALIDATING);
            var validationResult = validation.validate(result.invoice());
            job.complete(mapper.writeValueAsString(result.invoice()), mapper.writeValueAsString(validationResult.payload()),
                    result.confidence(), result.engine(), validationResult.reviewRequired());
            audit.save(new AuditEvent(jobId, job.getStatus().name(), "system",
                    "Extraction completed using " + result.engine() + "; confidence=" + result.confidence()));
        } catch (Exception failure) {
            job.fail(failure.getMessage());
            audit.save(new AuditEvent(jobId, "PROCESSING_FAILED", "system", "Pipeline failure recorded; inspect server diagnostics by correlation id"));
        }
        jobs.save(job);
    }
}
