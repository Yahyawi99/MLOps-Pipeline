# Stage 1: Grab the official Python 3.10.0 image to extract pre-compiled binaries
FROM python:3.10.0-slim as python-binaries

# Stage 2: Build the actual Jenkins image
FROM jenkins/jenkins:lts

USER root

# Copy the compiled Python binaries and libraries from Stage 1 into the Jenkins image
COPY --from=python-binaries /usr/local /usr/local

# Update dynamic linker run-time bindings so the OS finds the new Python libraries
# Also, install any lightweight system packages your Python environment might still need
RUN ldconfig && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    # Optional: Add any missing C-libraries your specific python packages might require here
    && rm -rf /var/lib/apt/lists/*

# Verify the installation works (this also checks that symlinks like `python3` work)
RUN python3 --version && pip3 --version

# Drop back to the jenkins user for security
USER jenkins