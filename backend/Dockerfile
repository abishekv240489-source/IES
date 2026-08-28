FROM maven:3.9-eclipse-temurin-21-alpine AS build
WORKDIR /workspace
COPY pom.xml ./
RUN mvn --batch-mode --no-transfer-progress dependency:go-offline
COPY src ./src
RUN mvn --batch-mode --no-transfer-progress -DskipTests package

FROM eclipse-temurin:21-jre-alpine AS runtime
RUN addgroup -S -g 10001 ies && adduser -S -D -H -u 10001 -G ies ies \
    && mkdir -p /var/lib/ies/invoices \
    && chown -R ies:ies /var/lib/ies
WORKDIR /app
COPY --from=build --chown=ies:ies /workspace/target/ies-api-*.jar /app/ies-api.jar
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/actuator/health/readiness || exit 1
ENTRYPOINT ["java", "-XX:+UseContainerSupport", "-XX:MaxRAMPercentage=75.0", "-Djava.security.egd=file:/dev/urandom", "-jar", "/app/ies-api.jar"]
