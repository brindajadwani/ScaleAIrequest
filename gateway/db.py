async def get_metrics(pool):
    async with pool.acquire() as conn:
        recent = await conn.fetchval(
            "SELECT COUNT(*) FROM requests WHERE created_at >= now() - interval '10 seconds'"
        )

        row = await conn.fetchrow("SELECT AVG(latency_ms) as avg_l, COUNT(*) as total FROM requests")
        avg_latency = float(row["avg_l"] or 0)
        total = row["total"] or 0

        failed = await conn.fetchval("SELECT COUNT(*) FROM requests WHERE status='failed'")
        error_rate = (failed / total * 100) if total else 0

        by_tool_rows = await conn.fetch(
            """
            SELECT routed_to,
                   COUNT(*) as count,
                   AVG(latency_ms) as avg_latency,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures
            FROM requests
            GROUP BY routed_to
            """
        )
        by_tool = []
        for r in by_tool_rows:
            d = dict(r)
            d["avg_latency"] = round(float(d["avg_latency"] or 0), 2)
            by_tool.append(d)

        latency_rows = await conn.fetch("SELECT latency_ms FROM requests ORDER BY id DESC LIMIT 500")
        latencies = sorted(r["latency_ms"] for r in latency_rows)
        p95 = 0
        if latencies:
            idx = min(int(len(latencies) * 0.95), len(latencies) - 1)
            p95 = latencies[idx]

        recent_rows = await conn.fetch(
            "SELECT latency_ms, status, routed_to FROM requests ORDER BY id DESC LIMIT 30"
        )
        recent_list = [dict(r) for r in recent_rows]
        recent_list.reverse()

        return {
            "rps_last_10s": round((recent or 0) / 10, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": p95,
            "total_requests": total,
            "error_rate_pct": round(error_rate, 2),
            "by_tool": by_tool,
            "recent": recent_list,
        }
