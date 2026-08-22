import io
import time
import asyncio
import gc
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from optimum.intel.openvino import OVStableDiffusionPipeline

app = FastAPI(title="CPU Text-to-Image API (Auto-Unloading)")

executor = ThreadPoolExecutor(max_workers=1)
generation_lock = asyncio.Lock()
active_queue_count = 0
counter_lock = asyncio.Lock()

MODEL_PATH = Path("/app/model")
pipe = None
last_active_time = time.time()

IDLE_TIMEOUT_SECONDS = 300  # Unload model after 5 minutes of inactivity

def load_model():
    """Loads the model into RAM only when needed."""
    global pipe
    if pipe is None:
        print("Model not in RAM. Loading and compiling OpenVINO graph (this will take 20-40s)...")
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
        print("Model loaded into RAM!")

def unload_model():
    """Deletes the model from RAM and forces garbage collection."""
    global pipe
    if pipe is not None:
        print(f"API idle for {IDLE_TIMEOUT_SECONDS}s. Unloading model to free RAM...")
        del pipe
        pipe = None
        gc.collect()  # Force Python to release memory back to Linux

async def idle_monitor():
    """Background task that checks if the API has been idle."""
    global last_active_time, pipe
    while True:
        await asyncio.sleep(30)
        # Only unload if the model is currently loaded AND we've passed the idle timeout
        if pipe is not None and (time.time() - last_active_time) > IDLE_TIMEOUT_SECONDS:
            unload_model()

@app.on_event("startup")
async def startup_event():
    # Start the background idle monitor when FastAPI boots
    asyncio.create_task(idle_monitor())

class ImageRequest(BaseModel):
    prompt: str
    steps: int = 1
    guidance_scale: float = 0.0

def generate_sync(prompt: str, steps: int, guidance_scale: float) -> bytes:
    load_model() # Will instantly pass if already loaded, or load if idle
    
    image = pipe(
        prompt=prompt,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        width=512,
        height=512
    ).images[0]

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
            last_active_time = time.time() # Update activity timer
            start_t = time.perf_counter()

            img_bytes = await loop.run_in_executor(
                executor, 
                generate_sync, 
                req.prompt, 
                req.steps, 
                req.guidance_scale
            )

            print(f"[Generation] Completed in {time.perf_counter() - start_t:.2f}s!")
            last_active_time = time.time() # Update activity timer again after generation
            return Response(content=img_bytes, media_type="image/jpeg")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            async with counter_lock:
                active_queue_count -= 1
