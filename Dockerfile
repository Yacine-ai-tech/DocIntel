FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install prebuilt llama-server for Surya OCR (llama.cpp backend)
RUN curl -sL https://github.com/ggml-org/llama.cpp/releases/download/b11529/llama-b11529-bin-ubuntu-x64.tar.gz -o /tmp/llama.tar.gz && \
    mkdir -p /tmp/llama && \
    tar -xzf /tmp/llama.tar.gz -C /tmp/llama && \
    cp /tmp/llama/llama-b11529/llama-server /tmp/llama/llama-b11529/llama-quantize /usr/local/bin/ && \
    cp /tmp/llama/llama-b11529/*.so* /usr/local/bin/ && \
    cp /tmp/llama/llama-b11529/*.so* /usr/local/lib/ && \
    ldconfig && \
    rm -rf /tmp/llama /tmp/llama.tar.gz

WORKDIR /app

COPY requirements.txt .
# CPU-only PyTorch first: the default Linux wheel bundles CUDA libraries that add several
# gigabytes and are never used here.
RUN pip install --upgrade pip uv && \
    uv pip install --system --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache-dir -r requirements.txt

# Surya OCR model, prepared at build time: the GGUF is fetched once and quantized (Q4_K_M by
# default: about a third of the F16 size and about 40% faster on CPU, with identical output on
# the invoice and dense-table pages used to check it), so nothing is downloaded or converted
# when the service starts and there is no model cold start.
ARG SURYA_QUANT=Q4_K_M
ENV SURYA_GGUF_LOCAL_MODEL_PATH=/opt/surya/surya-2.gguf \
    SURYA_GGUF_LOCAL_MMPROJ_PATH=/opt/surya/surya-2-mmproj.gguf
RUN mkdir -p /opt/surya && python -c "\
from huggingface_hub import hf_hub_download; import shutil; \
repo='datalab-to/surya-ocr-2-gguf'; \
m=hf_hub_download(repo,'surya-2.gguf'); \
shutil.copy(hf_hub_download(repo,'surya-2-mmproj.gguf'),'/opt/surya/surya-2-mmproj.gguf'); \
open('/tmp/surya_f16','w').write(m)" && \
    llama-quantize "$(cat /tmp/surya_f16)" /opt/surya/surya-2.gguf "${SURYA_QUANT}" && \
    rm -rf /root/.cache/huggingface /tmp/surya_f16

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=10s --start-period=240s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8001}/ready || exit 1

# Honor an injected $PORT; default 8001.
# exec via sh so $PORT expands AND uvicorn becomes PID 1 (clean SIGTERM shutdown).
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8001} --workers 1"]
