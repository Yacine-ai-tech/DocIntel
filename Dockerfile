FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra \
    poppler-utils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install prebuilt llama-server for Surya OCR (llama.cpp backend)
RUN curl -sL https://github.com/ggml-org/llama.cpp/releases/download/b11529/llama-b11529-bin-ubuntu-x64.tar.gz -o /tmp/llama.tar.gz && \
    mkdir -p /tmp/llama && \
    tar -xzf /tmp/llama.tar.gz -C /tmp/llama && \
    cp /tmp/llama/llama-b11529/llama-server /usr/local/bin/ && \
    cp /tmp/llama/llama-b11529/*.so* /usr/local/bin/ && \
    cp /tmp/llama/llama-b11529/*.so* /usr/local/lib/ && \
    ldconfig && \
    rm -rf /tmp/llama /tmp/llama.tar.gz

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip uv && \
    uv pip install --system --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/health || exit 1

# Honor the platform-injected $PORT (Render/Fly/Heroku); default 8001 locally.
# exec via sh so $PORT expands AND uvicorn becomes PID 1 (clean SIGTERM shutdown).
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1"]
