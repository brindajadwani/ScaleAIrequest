import asyncio
import random

from fastapi import FastAPI

app = FastAPI(title="Mock Tool A (fast)")


@app.post("/run")
async def run(payload: dict):
    await asyncio.sleep(random.uniform(0.1, 0.3))
    return {"tool": "tool_a", "echo": payload, "note": "fast & reliable"}


@app.get("/health")
async def health():
    return {"status": "ok"}
