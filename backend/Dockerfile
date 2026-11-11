# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project first
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the quantum_simulator package (editable)
RUN pip install -e ./quantum_simulator

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# Fewer glibc malloc arenas: keeps RSS of multi-threaded workers (threadpool +
# numpy) from ballooning. Each worker already holds cirq/qiskit/pennylane.
ENV MALLOC_ARENA_MAX=2
# Runtime knobs read by backend/start.py (override in the task definition):
#   WEB_CONCURRENCY             worker processes (default min(4, CPUs), capped by memory limit)
#   FORWARDED_ALLOW_IPS         proxies trusted for X-Forwarded-* (default "*")
#   UVICORN_TIMEOUT_KEEP_ALIVE  must exceed the ALB idle timeout (default 75s)

# Run the application
CMD ["python", "backend/start.py"]
