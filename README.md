c# ScalexAI v2 — Redis + Postgres + Docker (Horizontally Scalable)

This is the "real infrastructure" version of ScalexAI. Instead of an
in-process queue and SQLite, this version uses:

- **Redis** as a shared task queue + circuit-breaker state store
- **PostgreSQL** as the metrics/log database
- **Multiple worker containers** that pull from the same Redis queue —
  this is the actual horizontal scaling demo
- **Docker Compose** to run the entire stack with one command

```
                ┌──────────────┐
   client ───▶  │   gateway     │──▶ Redis (task_queue, results, health)
                │ (FastAPI)     │
                └──────┬────────┘
                       │ /api/metrics
                       ▼
                  PostgreSQL
                       ▲
   ┌─────────┬─────────┼─────────┐
   │ worker  │ worker  │ worker  │  (scale this with --scale worker=N)
   └────┬────┴────┬────┴────┬────┘
        ▼         ▼         ▼
     tool_a    tool_b    tool_c
     (fast)    (slow)    (flaky)
```

## What's included

```
scalexai-redis/
├── docker-compose.yml
├── init.sql              Postgres schema (auto-applied on first run)
├── gateway/              FastAPI gateway: enqueues tasks, serves metrics + dashboard
│   ├── main.py
│   ├── db.py             Postgres metrics queries
│   ├── router.py         shared routing + circuit breaker (Redis-backed)
│   ├── requirements.txt
│   └── Dockerfile
├── worker/                pulls tasks from Redis, calls tools, logs to Postgres
│   ├── worker.py
│   ├── router.py
│   ├── requirements.txt
│   └── Dockerfile
├── mock_tools/             3 simulated tools (fast / slow / flaky)
│   ├── tool_a.py, tool_b.py, tool_c.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── index.html         live dashboard (same as v1)
└── load_testing/
    └── locustfile.py
```

---

## 1. Install Docker on Windows

1. Download **Docker Desktop for Windows**: https://www.docker.com/products/docker-desktop/
2. Run the installer. It will ask to enable **WSL 2** (Windows Subsystem for
   Linux) — accept this, it's required and Docker installs it for you.
3. Restart your computer if prompted.
4. Launch Docker Desktop. Wait until it says "Docker Desktop is running"
   (the whale icon in the system tray stops animating).
5. Verify it works — open Command Prompt and run:
   ```bat
   docker --version
   docker compose version
   ```
   Both should print version numbers. If you get an error, Docker Desktop
   probably isn't fully started yet — wait a minute and try again.

That's the entire install. You do **not** need to separately install Redis,
PostgreSQL, or Python for this version — Docker builds and runs everything
in containers.

---

## 2. Run the whole stack

Unzip the project, open Command Prompt in the `scalexai-redis` folder, and
run:

```bat
docker compose up --build
```

First run will take a few minutes (downloading base images, installing
Python packages inside containers). You'll see logs from all services
interleaved. Wait until you see the gateway log line:

```
gateway-1  | INFO:     Application startup complete.
```

Then open your browser to:

```
http://localhost:8000
```

You'll see the live dashboard — same as v1, but now backed by Redis +
Postgres + containerized workers.

To run it in the background instead (so it doesn't take over your terminal):

```bat
docker compose up --build -d
```

View logs anytime with:

```bat
docker compose logs -f
```

---

## 3. Send test requests

From a new Command Prompt:

```bat
curl -X POST http://localhost:8000/api/task -H "Content-Type: application/json" -d "{\"task_type\":\"fast\"}"
curl -X POST http://localhost:8000/api/task -H "Content-Type: application/json" -d "{\"task_type\":\"slow\"}"
curl -X POST http://localhost:8000/api/task -H "Content-Type: application/json" -d "{\"task_type\":\"flaky\"}"
curl http://localhost:8000/api/metrics
```

Watch the dashboard update live.

---

## 4. Horizontal scaling — the main point of this version

By default, `docker-compose.yml` runs **one** worker container. Scale it up
to multiple workers with a single command, with zero code changes:

```bat
docker compose up --build -d --scale worker=5
```

All 5 worker containers pull from the **same Redis queue** — this is real
horizontal scaling, not a simulation. Run a load test (below) at 1 worker,
then at 5, then at 10, and compare average latency / queue depth on the
dashboard. This comparison is your "Workers vs Avg Latency" table for the
resume.

To scale back down:

```bat
docker compose up -d --scale worker=1
```

---

## 5. Load testing with Locust

Locust isn't included in the containers (to keep images small) — run it
from your host machine. You need Python installed locally for this part
only:

```bat
pip install locust
locust -f load_testing\locustfile.py --host http://localhost:8000
```

Open `http://localhost:8089`, set users (try 50, 200, 1000) and spawn rate,
and watch the dashboard at `http://localhost:8000` react in real time.

Headless version (no web UI):

```bat
locust -f load_testing\locustfile.py --host http://localhost:8000 --headless -u 200 -r 20 --run-time 30s
```

---

## 6. Stopping everything

```bat
docker compose down
```

This stops and removes the containers but keeps your Postgres data (stored
in a Docker volume). To wipe everything including the database:

```bat
docker compose down -v
```

---

## 7. Suggested experiments for your "scalability results"

1. **Baseline**: `docker compose up -d --scale worker=1`, run Locust with
   50 users for 30s, record avg latency, p95, RPS, error rate from the
   dashboard / Locust output.
2. **Scale workers**: repeat with `--scale worker=3`, then `--scale worker=10`,
   same Locust settings each time. Record results in a table.
3. **Circuit breaker under load**: tool_c fails ~15% of the time. At high
   load, watch the "Tool health" panel — after 3 consecutive failures its
   circuit opens for 15s and traffic reroutes to tool_a. You'll see
   `tool_c` failures pause and `tool_a` count spike during that window.
4. **Queue depth vs workers**: with 1 worker, send a burst (e.g. 500 users)
   and watch "Queue depth" climb high and drain slowly. With 10 workers,
   the same burst should barely move the queue depth — this is the clearest
   visual proof of horizontal scaling.
5. **Resilience**: stop a tool container mid-test
   (`docker compose stop tool_b`) and confirm requests routed to it fail
   gracefully (status `"failed"` in the result) without crashing the
   gateway or workers. Restart it with `docker compose start tool_b`.

---

## Configuration

- **Routing rules**: `ROUTES` in `gateway/router.py` and `worker/router.py`
  (keep both in sync — they must match)
- **Circuit breaker**: `FAILURE_THRESHOLD`, `COOLDOWN_SECONDS` in the same
  files
- **Tool latency/failure simulation**: `mock_tools/tool_a.py` / `tool_b.py`
  / `tool_c.py`
- **Ports**: change the left-hand side of `"8000:8000"` etc. in
  `docker-compose.yml` if a port is already in use on your machine

---

## Troubleshooting

- **"docker: command not found" / Docker Desktop not starting**: make sure
  Docker Desktop is running (check system tray) before running
  `docker compose` commands. On first install it can take a minute to
  initialize.
- **Port already in use (8000, 5432, 6379)**: another program is using that
  port. Either close it, or change the host-side port in
  `docker-compose.yml`, e.g. `"8001:8000"` for the gateway, then browse to
  `http://localhost:8001`.
- **`docker compose up` fails on `condition: service_healthy`**: this needs
  a reasonably recent Docker Compose (v2.20+). Update Docker Desktop if you
  hit this.
- **Dashboard shows "disconnected"**: the gateway container isn't ready yet
  — check `docker compose logs gateway`.
- **Requests stuck / timeout after 15s**: no worker is running, or workers
  can't reach the mock tools — check `docker compose logs worker`.
- **Postgres data looks stale between runs**: data persists in the `pgdata`
  volume. Use `docker compose down -v` to start completely fresh.

---

## How this differs from v1 (no-Docker version)

| | v1 (plain Python) | v2 (this version) |
|---|---|---|
| Queue | in-process `asyncio.Queue` | Redis (shared across containers) |
| Database | SQLite | PostgreSQL |
| Workers | async tasks inside gateway process | separate, independently scalable containers |
| Circuit breaker state | in-memory (single process) | Redis (shared across all workers) |
| Run command | `python -m uvicorn ...` ×4 | `docker compose up` |
| Horizontal scaling | not possible | `docker compose up --scale worker=N` |

Both versions share the same dashboard and API shape, so anything you built
on top of v1 (Locust tests, dashboard tweaks) works unchanged here.

## Next steps

- Add **Prometheus + Grafana** containers to `docker-compose.yml` for
  production-grade monitoring (scrape `/api/metrics` or add a
  `/metrics` endpoint in Prometheus exposition format using
  `prometheus-fastapi-instrumentator`).
- Replace the rule-based router with a **LangGraph** agent.
- Deploy to **Kubernetes** using the same images — each service here maps
  directly to a Deployment, and `--scale worker=N` becomes an HPA
  (Horizontal Pod Autoscaler) on the worker Deployment.
