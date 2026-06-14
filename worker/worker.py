"""
ScalexAI worker process.

Run multiple copies of this (docker-compose --scale worker=N) to scale
horizontally. Each worker:
  1. Blocks on Redis queue "task_queue" for a new task
  2. Selects a route (rule-based + circuit breaker, state shared via Redis)
  3. Calls the chosen mock tool over HTTP
  4. Logs the outcome to Postgres
  5. Pushes the result back to Redis so the gateway can return it
"""

import asyncio
import json
import os
import time

import asyncpg
import httpx
import redis.asyncio as aioredis

import router as route_module

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://scalexai:scalexai@postgres:5432/scalexai")
WORKER_ID = os.environ.get("HOSTNAME", "worker")


async def main():
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

    # retry DB connection until postgres is ready
    pool = None
    while pool is None:
        try:
            pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        except Exception as e:
            print(f"[{WORKER_ID}] waiting for postgres... ({e})")
            await asyncio.sleep(2)

    print(f"[{WORKER_ID}] ready, waiting for tasks...")

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            _, raw = await redis_client.blpop("task_queue")
            task = json.loads(raw)

            task_type = task.get("task_type", "fast")
            request_id = task.get("request_id")
            enqueued_at = task.get("enqueued_at", time.time())
            queue_wait_ms = int((time.time() - enqueued_at) * 1000)

            route, key = await route_module.select_route(redis_client, task_type)

            start = time.time()
            status = "success"
            try:
                resp = await client.post(route["url"], json=task)
                resp.raise_for_status()
                result = resp.json()
                await route_module.report_result(redis_client, key, True)
            except Exception as e:
                status = "failed"
                result = {"error": str(e)}
                await route_module.report_result(redis_client, key, False)

            latency_ms = int((time.time() - start) * 1000)

            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO requests (task_type, routed_to, status, latency_ms, queue_wait_ms) "
                    "VALUES ($1, $2, $3, $4, $5)",
                    task_type, route["name"], status, latency_ms, queue_wait_ms,
                )

            if request_id:
                payload = {
                    "status": status,
                    "routed_to": route["name"],
                    "worker": WORKER_ID,
                    "latency_ms": latency_ms,
                    "queue_wait_ms": queue_wait_ms,
                    "result": result,
                }
                await redis_client.rpush(f"result:{request_id}", json.dumps(payload))
                await redis_client.expire(f"result:{request_id}", 30)


if __name__ == "__main__":
    asyncio.run(main())
