# Stage 1: Build the Python environment
FROM python:3.10-slim-bookworm AS python-base
FROM jenkins/jenkins:lts

USER root
COPY --from=python-base /usr/local /usr/local

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl procps && rm -rf /var/lib/apt/lists/*

# Bake Python requirements (The slow part, done only once!)
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install "setuptools<70.0.0" && \
    python3 -m pip install -r /tmp/requirements.txt

# CRITICAL: Fix the "Sentinel" crash by pinning these versions
RUN python3 -m pip install "click<8.1.0" "typer==0.9.0"

USER jenkins