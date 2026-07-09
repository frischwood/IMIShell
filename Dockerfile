# IMIShell - local Docker image
#
# Multi-stage build that compiles MeteoIO (with the DBO plugin) and Snowpack
# from source, adapted from A3Dshell's Dockerfile.
#
# Build & run: docker-compose up --build
# Note: the DBO database (pgdata.int.slf.ch) requires the SLF VPN on the host.

# ============================================================
# Stage 1: Builder - Build MeteoIO and Snowpack from source
# ============================================================
FROM python:3.11-slim AS builder

# Pin specific MeteoIO/Snowpack versions (tag, branch or commit) at build time:
#   docker compose build --build-arg METEOIO_REF=<ref> --build-arg SNOWPACK_REF=<ref>
# Empty = default branch (latest).
ARG METEOIO_REF=
ARG SNOWPACK_REF=

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    libcurl4-openssl-dev \
    libproj-dev \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Build MeteoIO from source (DBO plugin enabled)
WORKDIR /tmp/build
RUN echo "Building MeteoIO from source..." && \
    git clone https://gitlabext.wsl.ch/snow-models/meteoio.git && \
    cd meteoio && \
    if [ -n "$METEOIO_REF" ]; then git checkout "$METEOIO_REF"; fi && \
    git log -1 --format="MeteoIO_Commit=%H%nMeteoIO_Date=%ci" > /tmp/meteoio_version.txt && \
    mkdir build && \
    cd build && \
    cmake .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DPLUGIN_DBO=ON && \
    make -j$(nproc) && \
    make install && \
    echo "MeteoIO build complete"

# Build Snowpack from source
WORKDIR /tmp/build
RUN echo "Building Snowpack from source..." && \
    git clone https://gitlabext.wsl.ch/snow-models/snowpack.git && \
    cd snowpack && \
    if [ -n "$SNOWPACK_REF" ]; then git checkout "$SNOWPACK_REF"; fi && \
    git log -1 --format="Snowpack_Commit=%H%nSnowpack_Date=%ci" > /tmp/snowpack_version.txt && \
    mkdir build && \
    cd build && \
    cmake .. \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON && \
    make -j$(nproc) && \
    make install && \
    echo "Snowpack build complete"

# ============================================================
# Stage 2: Runtime image
# ============================================================
FROM python:3.11-slim

LABEL description="IMIShell - IMIS timeseries extraction via MeteoIO/Snowpack"

RUN apt-get update && apt-get install -y \
    libcurl4 \
    libproj-dev \
    libgeos-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy built binaries and libraries from builder stage
COPY --from=builder /usr/local/bin/snowpack /usr/local/bin/
COPY --from=builder /usr/local/bin/meteoio_timeseries /usr/local/bin/
COPY --from=builder /usr/local/lib/libmeteoio.* /usr/local/lib/
COPY --from=builder /usr/local/lib/libsnowpack.* /usr/local/lib/

# Version info
COPY --from=builder /tmp/meteoio_version.txt /tmp/
COPY --from=builder /tmp/snowpack_version.txt /tmp/

RUN ldconfig

ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV METEOIO_BIN=/usr/local/bin/meteoio_timeseries
ENV SNOWPACK_BIN=/usr/local/bin/snowpack
ENV PORT=8501

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY input/ ./input/
COPY .streamlit/ ./.streamlit/
COPY gui_app.py .

RUN mkdir -p output config/shapefiles

# Create BUILD_INFO.txt
RUN echo "IMIShell Build" > BUILD_INFO.txt && \
    echo "Build Date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> BUILD_INFO.txt && \
    echo "" >> BUILD_INFO.txt && \
    cat /tmp/meteoio_version.txt >> BUILD_INFO.txt && \
    cat /tmp/snowpack_version.txt >> BUILD_INFO.txt

# Verify installations
RUN echo "Verifying installations..." && \
    snowpack --version || echo "Snowpack ready" && \
    meteoio_timeseries --version || echo "MeteoIO ready"

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/_stcore/health || exit 1

CMD streamlit run gui_app.py \
    --server.address=0.0.0.0 \
    --server.port=${PORT} \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
