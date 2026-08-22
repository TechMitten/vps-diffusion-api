import io
import time
import asyncio
import gc
import torch
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from optimum.intel.openvino import OVStableDiffusionPipeline
from diffusers import AutoencoderTiny

app = FastAPI(title="CPU Text-to-Image API (TAESD + Auto-Unloading)")

executor = ThreadPoolExecutor(max_workers=1)
generation_lock = asyncio.Lock()
active_queue_count = 0
counter_lock = asyncio.Lock()

MODEL_PATH = Path("/app/model")
TAESD_PATH = Path("/app/taesd")

pipe = None
taesd = None
last_active_time = time.time()

IDLE_TIMEOUT_SECONDS = 300  # Unload model after 5 minutes of inactivity

def load_model():
    """Loads the model into RAM only when needed."""
    global pipe, taesd
    if pipe is None:
        print("Model not in RAM. Loading OpenVINO graph and TAESD...")
        pipe = OVStableDiffusionPipeline.from_pretrained(
            MODEL_PATH,
            export=False,
            compile=False,
            local_files_only=True,
            ov_config={
                "PERFORMANCE_HINT": "LATENCY",
                "INFERENCE_NUM_THREADS": "4",
                "NUM_STREAMS": "1"
            }
        )
        pipe.compile()
        
        # Load TAESD (takes ~100ms to decode on CPU)
        taesd = AutoencoderTiny.from_pretrained(TAESD_PATH, local_files_only=True)
        print("Models loaded into RAM!")

def unload_model():
    """Deletes the model from RAM and forces garbage collection."""
    global pipe, taesd
    if pipe is not None:
        print(f"API idle for {IDLE_TIMEOUT_SECONDS}s. Unloading model to free RAM...")
        del pipe
        del taesd
        pipe = None
        taesd = None
        gc.collect()  # Force Python to release memory back to Linux

async def idle_monitor():
    """Background task that checks if the API has been idle."""
    global last_active_time, pipe
    while True:
        await asyncio.sleep(30)
        if pipe is not None and (time.time() - last_active_time) > IDLE_TIMEOUT_SECONDS:
            unload_model()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(idle_monitor())

class ImageRequest(BaseModel):
    prompt: str
    steps: int = 1
    guidance_scale: float = 0.0

def generate_sync(prompt: str, steps: int, guidance_scale: float) -> bytes:
    load_model()
    
    # 1. Generate Latents using OpenVINO (Stops before the slow VAE step)
    result = pipe(
        prompt=prompt,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        width=512,
        height=512,
        output_type="latent"  # Crucial: Returns raw math, not a pixel image
    )
    latents = result.images

    # Convert to PyTorch tensor if OpenVINO returned a numpy array
    if isinstance(latents, np.ndarray):
        latents = torch.from_numpy(latents)
    
    # 2. Decode the latents to an image using TAESD
    latents = latents / 0.18215  # SD 1.5 standard scaling factor
    
    with torch.no_grad():
        image_tensor = taesd.decode(latents).sample
        
    # Use the built-in image processor to convert the tensor to a clean PIL image
    image = pipe.image_processor.postprocess(image_tensor, output_type="pil")[0]

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="JPEG", quality=85)
    return img_byte_arr.getvalue()

@app.post("/generate")
async def generate_image(req: ImageRequest):
    global active_queue_count, last_active_time
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    
    async with counter_lock:
        active_queue_count += 1

    loop = asyncio.get_event_loop()
    
    async with generation_lock:
        try:
            last_active_time = time.time()
            start_t = time.perf_counter()

            img_bytes = await loop.run_in_executor(
                executor, 
                generate_sync, 
                req.prompt, 
                req.steps, 
                req.guidance_scale
            )

            print(f"[Generation] Completed in {time.perf_counter() - start_t:.2f}s!")
            last_active_time = time.time()
            return Response(content=img_bytes, media_type="image/jpeg")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            async with counter_lock:
                active_queue_count -= 1
