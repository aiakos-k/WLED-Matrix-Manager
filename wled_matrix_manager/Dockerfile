# https://contributors.home-assistant.io/apps/guides/dockerfile/
# Since Supervisor 2026.04.0 BUILD_FROM is no longer passed automatically,
# so the base image is defined here as a default (multi-arch manifest).
ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Build Final Image
FROM $BUILD_FROM

# Install required tools
ARG TEMPIO_VERSION=2024.11.2
ARG TARGETARCH
RUN \
    if [ -z "${TARGETARCH}" ]; then \
        echo "TARGETARCH is not set, please use Docker BuildKit for the build." && exit 1; \
    fi \
    && case "${TARGETARCH}" in \
        amd64) tempio_arch="amd64" ;; \
        arm64) tempio_arch="aarch64" ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && apk add --no-cache \
        python3 \
        py3-pip \
        py3-pillow \
        py3-numpy \
        curl \
    && curl -sSLf -o /usr/bin/tempio \
        "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${tempio_arch}" \
    && chmod +x /usr/bin/tempio

# Install Python dependencies
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy backend code
COPY backend/ ./

# Create data directory for SQLite
RUN mkdir -p /data

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ../frontend/dist

# Copy root filesystem
COPY rootfs /

# Set working directory
WORKDIR /app

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# The Supervisor and the CI set io.hass.version and io.hass.arch.
LABEL \
    io.hass.type="addon" \
    io.hass.name="WLED Matrix Manager" \
    io.hass.description="Create and manage pixel-art scenes for WLED LED matrices" \
    org.opencontainers.image.title="Home Assistant WLED Matrix Manager Add-on" \
    org.opencontainers.image.description="Modernes Home Assistant Add-on mit FastAPI Backend und React Frontend" \
    org.opencontainers.image.source="https://github.com/aiakos-k/WLED-Matrix-Manager" \
    org.opencontainers.image.licenses="EUPL-1.2"
