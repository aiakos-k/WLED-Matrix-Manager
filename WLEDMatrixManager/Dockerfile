# https://developers.home-assistant.io/docs/add-ons/configuration#add-on-dockerfile
ARG BUILD_FROM

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
ARG TEMPIO_VERSION BUILD_ARCH
RUN \
    apk add --no-cache \
        python3 \
        py3-pip \
        py3-pillow \
        py3-numpy \
        curl \
    && \
    curl -sSLf -o /usr/bin/tempio \
    "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${BUILD_ARCH}" \
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

# Copy custom integration for HA
COPY custom_components /app/custom_components

# Copy root filesystem
COPY rootfs /

# Set working directory
WORKDIR /app

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
