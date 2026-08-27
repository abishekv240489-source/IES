package com.pil.ies.domain;

public enum JobStatus {
    QUEUED,
    PREPROCESSING,
    OCR_RUNNING,
    MAPPING,
    VALIDATING,
    PENDING_REVIEW,
    COMPLETED,
    FAILED,
    REJECTED
}
