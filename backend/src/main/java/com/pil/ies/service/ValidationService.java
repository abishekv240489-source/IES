package com.pil.ies.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.pil.ies.config.IesProperties;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Currency;

@Service
public class ValidationService {
    private final ObjectMapper mapper;
    private final IesProperties properties;

    public ValidationService(ObjectMapper mapper, IesProperties properties) {
        this.mapper = mapper;
        this.properties = properties;
    }

    public ValidationResult validate(JsonNode invoice) {
        ArrayNode issues = mapper.createArrayNode();
        require(invoice, "/header/invoiceNumber", "Invoice number", issues);
        require(invoice, "/header/invoiceDate", "Invoice date", issues);
        require(invoice, "/vendor/name", "Vendor name", issues);
        require(invoice, "/amounts/total", "Total amount", issues);
        checkConfidence(invoice, "", issues);
        checkCurrency(invoice.at("/header/currency/value"), issues);
        checkDate(invoice.at("/header/invoiceDate/value"), issues);
        checkAmounts(invoice, issues);
        boolean reviewRequired = issues.size() > 0;
        ObjectNode result = mapper.createObjectNode();
        result.put("reviewRequired", reviewRequired);
        result.set("issues", issues);
        result.put("ruleVersion", "2026.08.1");
        return new ValidationResult(result, reviewRequired);
    }

    private void require(JsonNode root, String pointer, String label, ArrayNode issues) {
        JsonNode value = root.at(pointer + "/value");
        if (value.isMissingNode() || value.isNull() || value.asText().isBlank()) issue(issues, pointer, "MISSING_REQUIRED", label + " is required", "BLOCK");
    }

    private void checkConfidence(JsonNode node, String path, ArrayNode issues) {
        if (node.isObject() && node.has("value") && node.has("confidence")) {
            if (!node.get("value").isNull() && node.path("confidence").asDouble(0) < properties.minFieldConfidence()) {
                issue(issues, path, "LOW_CONFIDENCE", "Field confidence is below " + properties.minFieldConfidence(), "WARN");
            }
            return;
        }
        if (node.isObject()) node.properties().forEach(entry -> checkConfidence(entry.getValue(), path + "/" + entry.getKey(), issues));
        if (node.isArray()) for (int i = 0; i < node.size(); i++) checkConfidence(node.get(i), path + "/" + i, issues);
    }

    private void checkCurrency(JsonNode value, ArrayNode issues) {
        if (value.isTextual() && !value.asText().isBlank()) {
            try { Currency.getInstance(value.asText().toUpperCase()); }
            catch (IllegalArgumentException invalid) { issue(issues, "/header/currency", "INVALID_CURRENCY", "Currency must be ISO 4217", "BLOCK"); }
        }
    }

    private void checkDate(JsonNode value, ArrayNode issues) {
        if (!value.isTextual() || value.asText().isBlank()) return;
        try {
            LocalDate date = LocalDate.parse(value.asText());
            if (date.isAfter(LocalDate.now()) || date.isBefore(LocalDate.now().minusDays(365)))
                issue(issues, "/header/invoiceDate", "DATE_SANITY", "Invoice date is outside the allowed range", "WARN");
        } catch (DateTimeParseException invalid) {
            issue(issues, "/header/invoiceDate", "INVALID_DATE", "Invoice date must use ISO format YYYY-MM-DD", "BLOCK");
        }
    }

    private void checkAmounts(JsonNode invoice, ArrayNode issues) {
        JsonNode lines = invoice.path("lineItems");
        if (!lines.isArray() || lines.isEmpty()) return;
        double sum = 0;
        for (JsonNode line : lines) sum += line.at("/amount/value").asDouble(0);
        double total = invoice.at("/amounts/total/value").asDouble(0);
        double tax = invoice.at("/amounts/tax/value").asDouble(0);
        if (Math.abs((sum + tax) - total) > 0.02)
            issue(issues, "/amounts/total", "AMOUNT_MISMATCH", "Line amounts plus tax do not reconcile to total", "BLOCK");
    }

    private static void issue(ArrayNode issues, String field, String code, String message, String severity) {
        ObjectNode issue = issues.addObject();
        issue.put("field", field);
        issue.put("code", code);
        issue.put("message", message);
        issue.put("severity", severity);
    }

    public record ValidationResult(JsonNode payload, boolean reviewRequired) {}
}
