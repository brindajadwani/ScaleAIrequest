import asyncio
import random

from fastapi import FastAPI

app = FastAPI(title="Mock Tool B (slow)")


@app.post("/run")
async def run(payload: dict):
    await asyncio.sleep(random.uniform(1.0, 2.5))
    return {"tool": "tool_b", "echo": payload, "note": "slow, simulates heavy model"}


@app.get("/health")
async def health():
    return {"status": "ok"}
