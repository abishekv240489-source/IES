package com.pil.ies.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pil.ies.api.ApiModels;
import com.pil.ies.domain.AuditEvent;
import com.pil.ies.domain.JobStatus;
import com.pil.ies.repository.AuditEventRepository;
import com.pil.ies.repository.InvoiceJobRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.util.EnumSet;
import java.util.List;
import java.util.UUID;

@Service
public class InvoiceService {
    private static final EnumSet<JobStatus> ACTIVE_OR_DONE = EnumSet.complementOf(EnumSet.of(JobStatus.FAILED, JobStatus.REJECTED));
    private final InvoiceJobRepository jobs;
    private final AuditEventRepository audit;
    private final FileIngestionService ingestion;
    private final PipelineOrchestrator pipeline;
    private final ValidationService validation;
    private final ObjectMapper mapper;

    public InvoiceService(InvoiceJobRepository jobs, AuditEventRepository audit, FileIngestionService ingestion,
                          PipelineOrchestrator pipeline, ValidationService validation, ObjectMapper mapper) {
        this.jobs = jobs;
        this.audit = audit;
        this.ingestion = ingestion;
        this.pipeline = pipeline;
        this.validation = validation;
        this.mapper = mapper;
    }

    public ApiModels.UploadResponse upload(List<MultipartFile> files, String actor) throws IOException {
        if (files == null || files.isEmpty() || files.size() > 100) throw new IllegalArgumentException("Upload between 1 and 100 files per batch");
        UUID batchId = UUID.randomUUID();
        var items = new java.util.ArrayList<ApiModels.UploadItem>();
        for (MultipartFile file : files) {
            var stored = ingestion.store(file);
            var duplicate = jobs.findFirstBySha256AndStatusIn(stored.sha256(), ACTIVE_OR_DONE);
            if (duplicate.isPresent()) {
                Files.deleteIfExists(stored.path());
                items.add(new ApiModels.UploadItem(duplicate.get().getId(), stored.originalFilename(), duplicate.get().getStatus(), true, "Identical document already exists"));
                continue;
            }
            var job = com.pil.ies.domain.InvoiceJob.queued(batchId, stored.originalFilename(), stored.storedFilename(),
                    stored.sha256(), stored.contentType(), stored.sizeBytes());
            jobs.save(job);
            audit.save(new AuditEvent(job.getId(), "UPLOADED", actor, "File accepted; sha256=" + stored.sha256()));
            items.add(new ApiModels.UploadItem(job.getId(), job.getOriginalFilename(), job.getStatus(), false, "Queued"));
            pipeline.process(job.getId());
        }
        return new ApiModels.UploadResponse(batchId, items);
    }

    public Page<ApiModels.JobResponse> list(JobStatus status, Pageable pageable) {
        return (status == null ? jobs.findAll(pageable) : jobs.findByStatus(status, pageable)).map(this::response);
    }

    public ApiModels.JobResponse get(UUID id) { return response(jobs.findById(id).orElseThrow()); }

    public List<ApiModels.AuditResponse> events(UUID id) {
        if (!jobs.existsById(id)) throw new java.util.NoSuchElementException("Invoice not found");
        return audit.findByJobIdOrderByCreatedAtAsc(id).stream().map(ApiModels.AuditResponse::from).toList();
    }

    @Transactional
    public ApiModels.JobResponse review(UUID id, ApiModels.ReviewRequest request, String actor) throws JsonProcessingException {
        var job = jobs.findById(id).orElseThrow();
        if (job.getStatus() != JobStatus.PENDING_REVIEW) throw new IllegalStateException("Only pending-review invoices can be reviewed");
        var validationResult = validation.validate(request.extraction());
        job.applyReview(mapper.writeValueAsString(request.extraction()), mapper.writeValueAsString(validationResult.payload()), request.approved());
        audit.save(new AuditEvent(id, request.approved() ? "REVIEW_APPROVED" : "REVIEW_REJECTED", actor,
                request.remarks() == null ? "" : request.remarks()));
        return response(job);
    }

    public ApiModels.DashboardResponse dashboard() {
        long processing = jobs.countByStatus(JobStatus.PREPROCESSING) + jobs.countByStatus(JobStatus.OCR_RUNNING)
                + jobs.countByStatus(JobStatus.MAPPING) + jobs.countByStatus(JobStatus.VALIDATING);
        return new ApiModels.DashboardResponse(jobs.count(), jobs.countByStatus(JobStatus.QUEUED), processing,
                jobs.countByStatus(JobStatus.PENDING_REVIEW), jobs.countByStatus(JobStatus.COMPLETED), jobs.countByStatus(JobStatus.FAILED),
                java.util.Map.of("fieldAccuracy", ">=95%", "throughput", ">=200 invoices/hour", "p95Latency", "<15 seconds", "status", "awaiting benchmark dataset"));
    }

    private ApiModels.JobResponse response(com.pil.ies.domain.InvoiceJob job) {
        return ApiModels.JobResponse.from(job, readJson(job.getExtractionJson()), readJson(job.getValidationJson()));
    }

    private JsonNode readJson(String value) {
        if (value == null || value.isBlank()) return null;
        try { return mapper.readTree(value); }
        catch (JsonProcessingException invalid) { throw new IllegalStateException("Stored JSON is invalid", invalid); }
    }
}
