FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    "optimum-intel[openvino]>=1.20.0" \
    "openvino>=2024.0.0" \
    "diffusers>=0.30.0" \
    "transformers<5.0.0" \
    "fastapi[standard]" \
    uvicorn \
    pillow

# Download SDXS and the Tiny AutoEncoder (TAESD)
RUN python3 -c '\
from optimum.intel.openvino import OVStableDiffusionPipeline; \
from diffusers import AutoencoderTiny; \
pipe = OVStableDiffusionPipeline.from_pretrained("rupeshs/sdxs-512-0.9-openvino", compile=False); \
pipe.save_pretrained("/app/model"); \
taesd = AutoencoderTiny.from_pretrained("madebyollin/taesd"); \
taesd.save_pretrained("/app/taesd"); \
'

COPY app.py .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
