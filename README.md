# ScalexAI

A horizontally scalable task-processing system built with a shared Redis queue, a PostgreSQL metrics store, and multiple independently scalable worker containers — all orchestrated with Docker Compose.

## Features

- **FastAPI gateway** that accepts task requests, enqueues them in Redis, and serves a live dashboard + metrics API.
- **Redis** used as a shared task queue and circuit-breaker state store, accessible by all workers at once.
- **PostgreSQL** used to persist task logs and metrics.
- **Multiple worker containers** that all pull from the same Redis queue — enabling real horizontal scaling with `docker compose up --scale worker=N`, no code changes required.
- **3 mock tools** (fast, slow, flaky) that workers call, simulating real-world latency and failure conditions.
- **Circuit breaker logic** (Redis-backed) that opens after repeated failures on a tool and reroutes traffic automatically.
- **Live dashboard** showing queue depth, tool health, and latency in real time.
- **Load testing** with Locust to benchmark performance at different worker counts.

## Architecture

```
client → gateway (FastAPI) → Redis (queue, results, health)
                ↓
            PostgreSQL (metrics/logs)
                ↑
    worker  worker  worker   (scale horizontally)
      ↓        ↓       ↓
   tool_a   tool_b   tool_c
   (fast)   (slow)   (flaky)
```

## Tech Stack

- FastAPI (gateway)
- Redis (queue + circuit breaker state)
- PostgreSQL (metrics/logs)
- Docker Compose (orchestration)
- Locust (load testing)

## How to Run

```bash
docker compose up --build
```

Then open `http://localhost:8000` for the dashboard.

Scale workers horizontally:

```bash
docker compose up --build -d --scale worker=5
```

## Key Result

Sending the same load burst with 1 worker vs 10 workers shows queue depth barely moving at 10 workers — direct proof of horizontal scaling with zero code changes, only container scaling.
