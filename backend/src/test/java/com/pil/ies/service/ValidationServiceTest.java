package com.pil.ies.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.pil.ies.config.IesProperties;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ValidationServiceTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final ValidationService service = new ValidationService(mapper,
            new IesProperties(Path.of("data"), 20_000_000, 20, "http://localhost", true, .70, List.of("http://localhost")));

    @Test
    void validInvoicePasses() throws Exception {
        var invoice = mapper.readTree("""
            {"header":{"invoiceNumber":{"value":"INV-1","confidence":0.99},"invoiceDate":{"value":"2026-08-20","confidence":0.99},"currency":{"value":"USD","confidence":0.99}},
             "vendor":{"name":{"value":"Supplier","confidence":0.99}},
             "amounts":{"tax":{"value":10,"confidence":0.99},"total":{"value":110,"confidence":0.99}},
             "lineItems":[{"amount":{"value":100,"confidence":0.99}}]}
            """);
        assertThat(service.validate(invoice).reviewRequired()).isFalse();
    }

    @Test
    void lowConfidenceAndMissingFieldsRequireReview() throws Exception {
        var invoice = mapper.readTree("""
            {"header":{"invoiceNumber":{"value":null,"confidence":0},"invoiceDate":{"value":"bad-date","confidence":0.4},"currency":{"value":"NOPE","confidence":0.4}},
             "vendor":{"name":{"value":"Supplier","confidence":0.5}},"amounts":{"total":{"value":5,"confidence":0.5}},"lineItems":[]}
            """);
        var result = service.validate(invoice);
        assertThat(result.reviewRequired()).isTrue();
        assertThat(result.payload().path("issues").size()).isGreaterThan(3);
    }
}
