# VPS Diffusion API

Transform your low-end, no-GPU VPS into a fully functional text-to-image API. VPS Diffusion API leverages OpenVINO and SDXS to run AI image generation directly on basic CPUs. Deploy your own reliable text-to-image generation endpoint on budget VPS hardware.

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

The container will automatically download the lightweight OpenVINO weights, compile the execution graph for your specific CPU, and perform a warm-up generation during startup so the first user request is not delayed.

## API Usage

Once the container is running, the endpoint is available on port 8000. You can generate an image by sending a standard HTTP POST request.

```bash
curl -X POST "http://<YOUR_VPS_IP>:8000/generate" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "A retro futuristic sports car on a neon highway", "steps": 1, "guidance_scale": 0.0}' \
     --output result.jpg

```

You can also navigate to `http://<YOUR_VPS_IP>:8000/docs` in your browser to access the interactive Swagger UI. This built-in documentation allows you to test prompts, adjust step counts, and view model output.

## Adjusting the memory limit in docker-compose.yml

The docker-compose.yml in this repository sets an example memory limit for the API service under `deploy.resources.limits.memory`. That value must be adapted to the amount of RAM available on your VPS — setting it too high can cause the container to exceed host memory and trigger the OOM killer during initial model load.

Recommended approach:

- Leave some RAM for the host OS and other processes. A safe rule of thumb is to reserve 512MB–1GB for the host and give the rest to the container. For machines with more RAM (>= 8GB) reserving 1GB is recommended; for smaller machines reserve at least 512MB.
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

Automated one-liner (calculates a safe memory value and updates docker-compose.yml in-place):

```bash
# calculates safe memory and replaces the memory: line in docker-compose.yml
total=$(free -m | awk '/^Mem:/{print $2}'); 
if [ "$total" -ge 8192 ]; then safe=$((total-1024));
elif [ "$total" -ge 4096 ]; then safe=$((total-512));
else safe=$((total*85/100)); fi; 
safe_str="${safe}M"; 
# replace the first memory: <value>M occurrence under the api service
sed -i -E "0,/^\s*memory:\s*[0-9]+M/ s//    memory: ${safe_str}/" docker-compose.yml && 
printf "Set docker-compose memory to %s (host total: %s MB)\n" "$safe_str" "$total"
```

Notes and troubleshooting:

- Docker Compose's `deploy` > `resources` > `limits` section is honored by Docker Swarm and some orchestrators; on single-node Docker Compose environments the `mem_limit` option (Compose v1) or cgroup settings may be used differently. The examples here are intended as a simple way to prevent assigning more memory than your host can safely provide. If you are using a different Compose file version, consult Docker Compose docs for the exact field your runtime honors.
- If the container exits with OOM or the host becomes unresponsive during model load, reduce the memory value and restart (`docker compose down && docker compose up -d --build`).
- Always keep at least 512MB free for the host; on low-memory systems you may need to add swap to avoid failures during initial model compilation.


