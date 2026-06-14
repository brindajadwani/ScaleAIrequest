"""
Rule-based routing + circuit breaker, with state shared across all
gateway/worker instances via Redis (so it works correctly with multiple
worker replicas).
"""

import os
import time

ROUTES = {
    "fast": {"url": os.environ.get("TOOL_A_URL", "http://tool_a:8000/run"), "name": "tool_a"},
    "slow": {"url": os.environ.get("TOOL_B_URL", "http://tool_b:8000/run"), "name": "tool_b"},
    "flaky": {"url": os.environ.get("TOOL_C_URL", "http://tool_c:8000/run"), "name": "tool_c"},
}

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 15


async def select_route(redis_client, task_type: str):
    """Return (route_dict, route_key), applying the circuit breaker."""
    key = task_type if task_type in ROUTES else "fast"
    route = ROUTES[key]

    open_until = await redis_client.get(f"health:{key}:open_until")
    if open_until and float(open_until) > time.time() and key != "fast":
        return ROUTES["fast"], "fast"

    return route, key


async def report_result(redis_client, key: str, success: bool):
    if success:
        await redis_client.set(f"health:{key}:failures", 0)
        await redis_client.delete(f"health:{key}:open_until")
    else:
        failures = await redis_client.incr(f"health:{key}:failures")
        if failures >= FAILURE_THRESHOLD:
            await redis_client.set(f"health:{key}:open_until", time.time() + COOLDOWN_SECONDS)


async def get_health(redis_client):
    now = time.time()
    result = {}
    for key in ROUTES:
        failures = await redis_client.get(f"health:{key}:failures")
        open_until = await redis_client.get(f"health:{key}:open_until")
        failures = int(failures) if failures else 0
        open_until_f = float(open_until) if open_until else 0.0
        result[key] = {
            "failures": failures,
            "circuit_open": open_until_f > now,
            "reopens_in_sec": max(0, round(open_until_f - now, 1)),
        }
    return result
