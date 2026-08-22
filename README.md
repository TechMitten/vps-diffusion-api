# VPS Diffusion API

Transform your low-end, no-GPU VPS into a fully functional text-to-image API. VPS Diffusion API leverages OpenVINO and SD-Turbo to run AI image generation directly on standard CPUs. Deploy your own production-ready AI endpoint on budget hardware.

## Features

* **CPU-Native Acceleration:** Utilizes Intel OpenVINO for graph optimization and thread affinity.
* **Single-Step Inference:** Powered by SD-Turbo for single-step diffusion trajectories.
* **Smart Memory Management:** Includes lazy loading and auto-unloading to free host RAM during idle periods.
* **Built-in Queue Management:** Asynchronous locking prevents CPU core contention and server-crashing request pileups.

## Minimum Hardware Requirements

To ensure stable model compilation and reliable execution, your host must meet these minimum specifications:

* **CPU:** 4 Dedicated vCPUs (x86 architecture required; Intel processors preferred for optimal AVX-512 utilization).
* **RAM:** 8 GB Memory (Anything lower risks the Linux Out-Of-Memory killer crashing the container during the initial model load).
* **Storage:** 20 GB NVMe SSD (Required for fast container booting and model weight caching).

## Quick Start

Deploying the API requires Docker and Docker Compose. Run the following commands on your server:

```bash
git clone [https://github.com/techmitten/vps-diffusion-api.git](https://github.com/techmitten/vps-diffusion-api.git)
cd vps-diffusion-api
docker compose up -d --build

```

The container will automatically download the OpenVINO weights, compile the execution graph for your specific CPU, and start the FastAPI service.

## API Usage

Once the container is running, the endpoint is available on port 8000. You can generate an image by sending a standard HTTP POST request:

```bash
curl -X POST "http://<YOUR_VPS_IP>:8000/generate" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A retro futuristic sports car on a neon highway", "steps": 1, "guidance_scale": 0.0}' \
     --output result.jpg

```

You can also navigate to `http://<YOUR_VPS_IP>:8000/docs` in your browser to access the interactive Swagger UI. This built-in documentation allows you to test prompts, adjust step counts, and view generated images directly in the browser.

## SD-Turbo Optimal Settings

For best results with SD-Turbo image generation, use the following recommended parameters:

| Parameter | Recommended Value | Reason |
| --- | --- | --- |
| `steps` | 1 | The network is explicitly calibrated for single-step inference. |
| `guidance_scale` | 0.0 | Guidance is distilled into the model; values >0.0 introduce distortion. |
| `resolution` | 512x512 | Fixed architectural positional encodings are optimized for 512px. |

## Adjusting the memory limit in docker-compose.yml

The `docker-compose.yml` in this repository sets an example memory limit for the API service under `deploy.resources.limits.memory`. That value must be adapted to the amount of RAM available on your host system.

Recommended approach:

* Leave some RAM for the host OS and other processes. A safe rule of thumb is to reserve 512MB–1GB for the host and give the rest to the container. For machines with more RAM (>= 8GB), reserving 1GB to 2GB is recommended.
* The `memory` value in `docker-compose.yml` expects a number plus a unit (for example `7000M` for 7000 megabytes). The compose example currently uses `memory: 7000M`.

Quick manual steps:

1. Check total RAM in megabytes:

```bash
free -m | awk '/^Mem:/{print $2}'

```

This prints the total installed RAM in MB.

2. Pick a safe value for the container. Example rules:

* If total RAM >= 8192 MB (8GB): `container_memory_mb = total_mb - 1024`
* Else if total RAM >= 4096 MB (4GB): `container_memory_mb = total_mb - 512`
* Else: `container_memory_mb = floor(total_mb * 0.85)`

3. Update `docker-compose.yml`, replacing the memory line under `deploy.resources.limits` with the chosen value, e.g.:

```yaml
    deploy:
      resources:
        limits:
          cpus: '3.8'
          memory: 6000M

```

Notes and troubleshooting:

* Docker Compose's `deploy` > `resources` > `limits` section is honored by Docker Swarm and modern Docker Compose (v2) environments using cgroup resource enforcement.
* If the container exits with OOM (Out Of Memory) or the host becomes unresponsive during model load, adjust the memory value and restart (`docker compose down && docker compose up -d --build`).
* Always keep at least 512MB free for the host; on low-memory systems you may need to enable a swap file to avoid allocation failures during initial OpenVINO model compilation.

## Adjusting the CPU (cpus) value in docker-compose.yml

The `cpus` field under `deploy.resources.limits` controls how many CPU cores (or fractional cores) the service may use. In `docker-compose.yml` this is expressed as a decimal (for example `cpus: '3.5'`).

Like memory, the `cpus` value should be chosen so the host keeps enough CPU resources for system tasks and background processes. Assigning all vCPUs to the container can make the host unresponsive during CPU-intensive inference workloads.

Recommended approach:

* Discover how many vCPUs are available:

```bash
nproc --all
# or
lscpu | awk '/^CPU\(s\):/ {print $2}'

```

* Safe sizing rules of thumb:
* If total vCPUs >= 8: set `container_cpus = total_vcpus - 1.0`
* Else if total vCPUs >= 4: set `container_cpus = total_vcpus - 0.5`
* Else: set `container_cpus = round(total_vcpus * 0.85, 1)`



These rules leave 1 CPU for larger hosts, 0.5 CPU for medium hosts, and ~15% headroom for very small hosts.

* Example: for an 8-vCPU VPS the recommended setting would be `cpus: '7.0'`. For a 4-vCPU VPS use `cpus: '3.5'`.

Quick manual update in `docker-compose.yml`:

```yaml
    deploy:
      resources:
        limits:
          cpus: '3.5'
          memory: 6000M

```

Notes and troubleshooting:

* The `cpus` limit is enforced as a CFS quota via Docker cgroups; behavior may vary depending on your host kernel and virtualization layer.
* If the container is CPU-starved (very slow request times), increase the `cpus` allocation and restart the service. If the host becomes sluggish during generation, lower the value slightly to yield time to system daemons.
* For multi-tenant or production environments, ensure you monitor steal time (`top` or `vmstat 1`) to confirm your hosting provider is not throttling heavy CPU bursts.

```
