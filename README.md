# VPS Diffusion API

Transform your low-end, no-GPU VPS into a fully functional text-to-image API. VPS Diffusion API leverages OpenVINO and SDXS to run AI image generation directly on basic CPUs. Deploy your own reliab[...]

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

The container will automatically download the lightweight OpenVINO weights, compile the execution graph for your specific CPU, and perform a warm-up generation during startup so the first user req[...]

## API Usage

Once the container is running, the endpoint is available on port 8000. You can generate an image by sending a standard HTTP POST request.

```bash
curl -X POST "http://<YOUR_VPS_IP>:8000/generate" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A retro futuristic sports car on a neon highway", "steps": 1, "guidance_scale": 0.0}' \
     --output result.jpg

```

You can also navigate to `http://<YOUR_VPS_IP>:8000/docs` in your browser to access the interactive Swagger UI. This built-in documentation allows you to test prompts, adjust step counts, and view[...]

## SDXS Optimal Settings

For best results with SDXS image generation, use the following recommended parameters:

| Parameter | Recommended Value | Reason |
|-----------|-------------------|--------|
| `steps` | 1 | The network is explicitly calibrated for single-step inference. |
| `guidance_scale` | 0.0 | Guidance is distilled into the model; values >0.0 introduce distortion. |
| `resolution` | 512x512 | SDXS-512 has fixed architectural positional encodings for 512px. |

## Adjusting the memory limit in docker-compose.yml

The docker-compose.yml in this repository sets an example memory limit for the API service under `deploy.resources.limits.memory`. That value must be adapted to the amount of RAM available on your[...]

Recommended approach:

- Leave some RAM for the host OS and other processes. A safe rule of thumb is to reserve 512MB–1GB for the host and give the rest to the container. For machines with more RAM (>= 8GB) reserving [...]
- The `memory` value in docker-compose.yml expects a number plus a unit (for example `7000M` for 7000 megabytes). The compose example currently uses `memory: 7000M`.

Quick manual steps:

1. Check total RAM in megabytes:

```bash
free -m | awk '/^Mem:/{print $2}'
```

This prints the total installed RAM in MB.

2. Pick a safe value for the container. Example rules:

- If total RAM >= 8192 MB (8GB): container_memory_mb = total_mb - 1024
- Else if total RAM >= 4096 MB (4GB): container_memory_mb = total_mb - 512
- Else: container_memory_mb = floor(total_mb * 0.85)

3. Update docker-compose.yml, replacing the memory line under `deploy.resources.limits` with the chosen value, e.g.:

```yaml
    deploy:
      resources:
        limits:
          cpus: '3.8'
          memory: 6000M
```

Notes and troubleshooting:

- Docker Compose's `deploy` > `resources` > `limits` section is honored by Docker Swarm and some orchestrators; on single-node Docker Compose environments the `mem_limit` option (Compose v1) or cg[...]
- If the container exits with OOM or the host becomes unresponsive during model load, reduce the memory value and restart (`docker compose down && docker compose up -d --build`).
- Always keep at least 512MB free for the host; on low-memory systems you may need to add swap to avoid failures during initial model compilation.


## Adjusting the CPU (cpus) value in docker-compose.yml

The `cpus` field under `deploy.resources.limits` controls how many CPU cores (or fractional cores) the service may use. In docker-compose.yml this is expressed as a decimal (for example `cpus: '3.[...]

Like memory, the `cpus` value should be chosen so the host keeps enough CPU for system tasks and background processes. Assigning all vCPUs to the container can make the host unresponsive during CP[...]

Recommended approach:

- Discover how many vCPUs are available:

```bash
nproc --all
# or
lscpu | awk '/^CPU\(s\):/ {print $2}'
```

- Safe sizing rules of thumb:

  - If total vCPUs >= 8: set container_cpus = total_vcpus - 1.0
  - Else if total vCPUs >= 4: set container_cpus = total_vcpus - 0.5
  - Else: set container_cpus = round(total_vcpus * 0.85, 1)

  These rules leave 1 CPU for larger hosts, 0.5 CPU for medium hosts, and ~15% headroom for very small hosts.

- Example: for an 8-vCPU VPS the recommended setting would be `cpus: '7.0'`. For a 4-vCPU VPS use `cpus: '3.5'`.

Quick manual update in docker-compose.yml:

```yaml
    deploy:
      resources:
        limits:
          cpus: '3.5'
          memory: 6000M
```

Notes and troubleshooting:

- The `cpus` limit is advisory for some runtimes and is enforced as a cgroup quota by Docker; behavior may vary by host kernel and Docker version.
- If the container is CPU-starved (very slow requests), increase the `cpus` value and restart the service. If the host becomes unresponsive, reduce the value and keep more headroom for the OS.
- For predictable isolation in production, consider running in an orchestrator that enforces resource limits strictly (e.g., Kubernetes with proper resource requests/limits).

