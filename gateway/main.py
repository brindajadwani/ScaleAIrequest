"""
ScalexAI gateway (Redis + Postgres version).

The gateway itself does NOT call tools or run workers - it just:
  1. Pushes incoming tasks onto a Redis queue (with a unique request_id)
  2. Waits (BLPOP) for the matching result, pushed by whichever worker
     processed it
  3. Serves /api/metrics (from Postgres + Redis) and the live dashboard

Run multiple `worker` containers to scale horizontal processing capacity
independently of the gateway.
"""

import asyncio
import json
import os
import time
import uuid

import asyncpg
import psutil
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.responses import FileResponse

import db
import router as route_module

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://scalexai:scalexai@postgres:5432/scalexai")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app = FastAPI(title="ScalexAI Gateway (Redis + Postgres)")

redis_client = None
pg_pool = None


@app.on_event("startup")
async def startup():
    global redis_client, pg_pool
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    while pg_pool is None:
        try:
            pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        except Exception:
            await asyncio.sleep(2)


@app.post("/api/task")
async def handle_task(payload: dict):
    """Submit a task and wait (up to 15s) for the worker's result."""
    request_id = str(uuid.uuid4())
    task = dict(payload)
    task["request_id"] = request_id
    task["enqueued_at"] = time.time()

    await redis_client.rpush("task_queue", json.dumps(task))

    res = await redis_client.blpop(f"result:{request_id}", timeout=15)
    if res is None:
        return {"status": "timeout", "request_id": request_id}
    return json.loads(res[1])


@app.post("/api/task/async")
async def handle_task_async(payload: dict):
    """Submit a task without waiting for the result (fire-and-forget)."""
    request_id = str(uuid.uuid4())
    task = dict(payload)
    task["request_id"] = request_id
    task["enqueued_at"] = time.time()
    await redis_client.rpush("task_queue", json.dumps(task))
    depth = await redis_client.llen("task_queue")
    return {"status": "queued", "request_id": request_id, "queue_depth": depth}


@app.get("/api/metrics")
async def metrics():
    m = await db.get_metrics(pg_pool)
    m["queue_depth"] = await redis_client.llen("task_queue")
    m["cpu_percent"] = psutil.cpu_percent(interval=0.1)
    m["memory_percent"] = psutil.virtual_memory().percent
    m["health"] = await route_module.get_health(redis_client)
    return m


@app.get("/")
async def dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
