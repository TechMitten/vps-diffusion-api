# VPS Diffusion API

Transform your low-end, no-GPU VPS into a fully functional text-to-image API. VPS Diffusion API leverages OpenVINO and SDXS to run AI image generation directly on basic CPUs. Deploy your own reliable AI endpoint on budget hardware! The system includes a built-in asynchronous queue to prevent CPU contention and memory crashes when multiple requests arrive simultaneously.

## Minimum Hardware Requirements

To ensure stable model compilation and reliable execution, your host must meet these minimum specifications:

* **CPU:** 4 Dedicated vCPUs (x86 architecture required; Intel processors preferred for optimal AVX-512 utilization).
* **RAM:** 8 GB Memory (Anything lower risks the Linux Out-Of-Memory killer crashing the container during the initial model load).
* **Storage:** 20 GB NVMe SSD (Required for fast container booting and model weight caching).

## Quick Start

Deploying the API requires Docker and Docker Compose. Run the following commands on your server:

```bash
git clone https://github.com/techmitten/vps-diffusion-api.git
cd vps-diffusion-api
docker compose up -d --build

```

The container will automatically download the lightweight OpenVINO weights, compile the execution graph for your specific CPU, and perform a warm-up generation during startup so the first user request is processed immediately.

## API Usage

Once the container is running, the endpoint is available on port 8000. You can generate an image by sending a standard HTTP POST request.

```bash
curl -X POST "http://<YOUR_VPS_IP>:8000/generate" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A retro futuristic sports car on a neon highway", "steps": 1, "guidance_scale": 0.0}' \
     --output result.jpg

```

You can also navigate to `http://<YOUR_VPS_IP>:8000/docs` in your browser to access the interactive Swagger UI. This built-in documentation allows you to test prompts, adjust step counts, and view generated images directly from your browser.
