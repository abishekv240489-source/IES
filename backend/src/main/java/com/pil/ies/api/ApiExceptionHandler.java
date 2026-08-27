package com.pil.ies.api;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.Map;
import java.util.NoSuchElementException;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    ResponseEntity<Map<String, Object>> badRequest(RuntimeException error, HttpServletRequest request) {
        return response(HttpStatus.BAD_REQUEST, error, request);
    }

    @ExceptionHandler(NoSuchElementException.class)
    ResponseEntity<Map<String, Object>> notFound(RuntimeException error, HttpServletRequest request) {
        return response(HttpStatus.NOT_FOUND, error, request);
    }

    private ResponseEntity<Map<String, Object>> response(HttpStatus status, RuntimeException error, HttpServletRequest request) {
        return ResponseEntity.status(status).body(Map.of("timestamp", Instant.now(), "status", status.value(),
                "error", status.getReasonPhrase(), "message", error.getMessage(), "path", request.getRequestURI()));
    }
}
