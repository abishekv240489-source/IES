package com.pil.ies.service;

import com.pil.ies.config.IesProperties;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

@Service
public class FileIngestionService {
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff");
    private final IesProperties properties;

    public FileIngestionService(IesProperties properties) {
        this.properties = properties;
    }

    public StoredUpload store(MultipartFile file) throws IOException {
        if (file.isEmpty()) throw new IllegalArgumentException("File is empty");
        if (file.getSize() > properties.maxFileBytes()) throw new IllegalArgumentException("File exceeds configured size limit");
        String original = safeDisplayName(file.getOriginalFilename());
        String extension = extensionOf(original);
        if (!ALLOWED_EXTENSIONS.contains(extension)) throw new IllegalArgumentException("Unsupported invoice file type");

        Path root = properties.storageRoot().toAbsolutePath().normalize();
        Files.createDirectories(root);
        String storedName = UUID.randomUUID() + extension;
        Path destination = root.resolve(storedName).normalize();
        if (!destination.startsWith(root)) throw new IllegalArgumentException("Unsafe storage path");

        MessageDigest digest = sha256();
        try (InputStream source = file.getInputStream(); DigestInputStream secured = new DigestInputStream(source, digest)) {
            Files.copy(secured, destination, StandardCopyOption.REPLACE_EXISTING);
        }
        try {
            validateMagic(destination, extension);
            String contentType = file.getContentType() == null ? MediaType.APPLICATION_OCTET_STREAM_VALUE : file.getContentType();
            return new StoredUpload(original, storedName, destination, HexFormat.of().formatHex(digest.digest()), contentType, file.getSize());
        } catch (RuntimeException failure) {
            Files.deleteIfExists(destination);
            throw failure;
        }
    }

    private static void validateMagic(Path path, String extension) throws IOException {
        byte[] prefix = new byte[8];
        int read;
        try (InputStream input = Files.newInputStream(path)) { read = input.read(prefix); }
        boolean valid = switch (extension) {
            case ".pdf" -> read >= 4 && prefix[0] == '%' && prefix[1] == 'P' && prefix[2] == 'D' && prefix[3] == 'F';
            case ".png" -> read >= 8 && (prefix[0] & 0xff) == 0x89 && prefix[1] == 'P' && prefix[2] == 'N' && prefix[3] == 'G';
            case ".jpg", ".jpeg" -> read >= 3 && (prefix[0] & 0xff) == 0xff && (prefix[1] & 0xff) == 0xd8 && (prefix[2] & 0xff) == 0xff;
            case ".tif", ".tiff" -> read >= 4 && ((prefix[0] == 'I' && prefix[1] == 'I') || (prefix[0] == 'M' && prefix[1] == 'M'));
            default -> false;
        };
        if (!valid) throw new IllegalArgumentException("File signature does not match its extension");
    }

    private static String safeDisplayName(String name) {
        if (name == null || name.isBlank()) return "invoice";
        String normalized = Path.of(name).getFileName().toString().replaceAll("[\\p{Cntrl}]", "").trim();
        return normalized.substring(0, Math.min(normalized.length(), 255));
    }

    private static String extensionOf(String name) {
        int index = name.lastIndexOf('.');
        return index < 0 ? "" : name.substring(index).toLowerCase(Locale.ROOT);
    }

    private static MessageDigest sha256() {
        try { return MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }

    public record StoredUpload(String originalFilename, String storedFilename, Path path, String sha256,
                               String contentType, long sizeBytes) {}
}
