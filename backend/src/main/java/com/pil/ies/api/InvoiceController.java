package com.pil.ies.api;

import com.pil.ies.domain.JobStatus;
import com.pil.ies.service.InvoiceService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
public class InvoiceController {
    private final InvoiceService invoices;

    public InvoiceController(InvoiceService invoices) { this.invoices = invoices; }

    @PostMapping(value = "/invoices", consumes = "multipart/form-data")
    public ResponseEntity<ApiModels.UploadResponse> upload(@RequestPart("files") List<MultipartFile> files,
                                                           Authentication authentication) throws IOException {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(invoices.upload(files, actor(authentication)));
    }

    @GetMapping("/invoices")
    public Page<ApiModels.JobResponse> list(@RequestParam(required = false) JobStatus status,
                                            @RequestParam(defaultValue = "0") int page,
                                            @RequestParam(defaultValue = "25") int size) {
        return invoices.list(status, PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), 100)));
    }

    @GetMapping("/invoices/{id}")
    public ApiModels.JobResponse get(@PathVariable UUID id) { return invoices.get(id); }

    @GetMapping("/invoices/{id}/events")
    public List<ApiModels.AuditResponse> events(@PathVariable UUID id) { return invoices.events(id); }

    @PatchMapping("/invoices/{id}/review")
    public ApiModels.JobResponse review(@PathVariable UUID id, @Valid @RequestBody ApiModels.ReviewRequest request,
                                        Authentication authentication) throws Exception {
        return invoices.review(id, request, actor(authentication));
    }

    @GetMapping("/dashboard")
    public ApiModels.DashboardResponse dashboard() { return invoices.dashboard(); }

    private static String actor(Authentication authentication) {
        return authentication == null ? "local-demo-user" : authentication.getName();
    }
}
