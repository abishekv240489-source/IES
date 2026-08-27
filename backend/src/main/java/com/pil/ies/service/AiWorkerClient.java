package com.pil.ies.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.pil.ies.config.IesProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;

@Service
public class AiWorkerClient {
    private static final Logger log = LoggerFactory.getLogger(AiWorkerClient.class);
    private final HttpClient client;
    private final ObjectMapper mapper;
    private final IesProperties properties;

    public AiWorkerClient(ObjectMapper mapper, IesProperties properties) {
        this.client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).version(HttpClient.Version.HTTP_1_1).build();
        this.mapper = mapper;
        this.properties = properties;
    }

    public ExtractionResult extract(UUID jobId, Path file, String originalFilename) {
        String boundary = "----IES" + UUID.randomUUID().toString().replace("-", "");
        byte[] prefix = ("--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"document_id\"\r\n\r\n" + jobId + "\r\n" +
                "--" + boundary + "\r\n" +
                "Content-Disposition: form-data; name=\"file\"; filename=\"" + file.getFileName() + "\"\r\n" +
                "Content-Type: application/octet-stream\r\n\r\n").getBytes(StandardCharsets.UTF_8);
        byte[] suffix = ("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8);
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(properties.aiWorkerUrl() + "/v1/extract"))
                    .timeout(Duration.ofSeconds(30))
                    .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                    .POST(HttpRequest.BodyPublishers.concat(HttpRequest.BodyPublishers.ofByteArray(prefix),
                            HttpRequest.BodyPublishers.ofFile(file), HttpRequest.BodyPublishers.ofByteArray(suffix)))
                    .build();
            HttpResponse<String> httpResponse = client.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (httpResponse.statusCode() < 200 || httpResponse.statusCode() >= 300) {
                log.warn("AI worker request rejected status={} response={}", httpResponse.statusCode(), httpResponse.body());
                if (!properties.aiDemoFallback()) throw new IllegalStateException("AI worker rejected the request");
                return demoResult(originalFilename);
            }
            JsonNode response = mapper.readTree(httpResponse.body());
            if (response == null || !response.has("invoice")) throw new IllegalStateException("AI worker returned an invalid response");
            return new ExtractionResult(response.path("invoice"), response.path("overall_confidence").asDouble(0),
                    response.path("engine").asText("paddleocr-qwen"));
        } catch (IOException | InterruptedException | IllegalStateException failure) {
            if (failure instanceof InterruptedException) Thread.currentThread().interrupt();
            log.warn("AI worker unavailable: {}", failure.getClass().getSimpleName());
            if (!properties.aiDemoFallback()) throw new IllegalStateException("AI worker unavailable", failure);
            return demoResult(originalFilename);
        }
    }

    private ExtractionResult demoResult(String filename) {
        ObjectNode root = mapper.createObjectNode();
        ObjectNode header = root.putObject("header");
        header.set("invoiceNumber", field(filename.replaceFirst("(?i)\\.(pdf|png|jpe?g|tiff?)$", ""), 0.55));
        header.set("invoiceDate", field(null, 0));
        header.set("dueDate", field(null, 0));
        header.set("currency", field("USD", 0.45));
        header.set("poReference", field(null, 0));
        ObjectNode vendor = root.putObject("vendor");
        vendor.set("name", field("Demo Supplier - review required", 0.40));
        vendor.set("address", field(null, 0));
        vendor.set("country", field(null, 0));
        vendor.set("taxRegistration", field(null, 0));
        ObjectNode amounts = root.putObject("amounts");
        amounts.set("subtotal", field(0, 0.35));
        amounts.set("tax", field(0, 0.35));
        amounts.set("total", field(0, 0.35));
        root.putArray("lineItems");
        return new ExtractionResult(root, 0.40, "demo-fallback");
    }

    private ObjectNode field(Object value, double confidence) {
        ObjectNode node = mapper.createObjectNode();
        if (value == null) node.putNull("value"); else node.set("value", mapper.valueToTree(value));
        node.put("confidence", confidence);
        node.put("source", "demo");
        return node;
    }

    public record ExtractionResult(JsonNode invoice, double confidence, String engine) {}
}
