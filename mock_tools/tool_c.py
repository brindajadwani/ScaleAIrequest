import asyncio
import random

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Mock Tool C (flaky)")


@app.post("/run")
async def run(payload: dict):
    await asyncio.sleep(random.uniform(0.3, 0.8))
    if random.random() < 0.15:
        raise HTTPException(status_code=500, detail="tool_c: simulated failure")
    return {"tool": "tool_c", "echo": payload, "note": "flaky, ~15% failure rate"}


@app.get("/health")
async def health():
    return {"status": "ok"}
