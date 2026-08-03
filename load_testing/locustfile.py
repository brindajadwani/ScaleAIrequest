from locust import HttpUser, between, events, task


class APIUser(HttpUser):
    """
    Simulates clients hitting the ScalexAI gateway.

    Run with:
        py -m locust -f load_testing/locustfile.py --host http://localhost:8000

    Built-in Locust UI:
        http://localhost:8089

    Custom ScalexAI page:
        http://localhost:8089/scalexai
    """

    wait_time = between(0.1, 0.5)

    @task(3)
    def fast_task(self):
        self._submit_task("fast")

    @task(2)
    def slow_task(self):
        self._submit_task("slow")

    @task(1)
    def flaky_task(self):
        self._submit_task("flaky")

    def _submit_task(self, task_type: str):
        with self.client.post(
            "/api/task",
            json={"task_type": task_type},
            name=f"/api/task [{task_type}]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return

            try:
                payload = response.json()
            except ValueError:
                response.failure("invalid JSON response")
                return

            status = payload.get("status")
            if status == "success":
                response.success()
            elif status == "timeout":
                response.failure("gateway timeout waiting for worker")
            elif status == "failed":
                response.failure(f"worker failed: {payload.get('routed_to', 'unknown tool')}")
            else:
                response.failure(f"unexpected status: {status}")


@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    if not environment.web_ui:
        return

    @environment.web_ui.app.route("/scalexai")
    def scalexai_page():
        host = environment.host or "http://localhost:8000"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ScalexAI Load Test Console</title>
  <style>
    :root {{
      --bg: #070b10;
      --panel: #121923;
      --line: #243041;
      --text: #e8eef6;
      --muted: #8b9cb0;
      --accent: #3dd6c6;
      --accent-2: #6ea8ff;
      --mono: "JetBrains Mono", ui-monospace, monospace;
      --sans: "Segoe UI", Inter, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(61,214,198,0.08), transparent 28%),
        radial-gradient(circle at top right, rgba(110,168,255,0.08), transparent 24%),
        var(--bg);
      padding: 32px;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; }}
    .brand {{
      font-family: var(--mono);
      letter-spacing: 0.08em;
      font-size: 18px;
      margin-bottom: 8px;
    }}
    .brand span {{ color: var(--accent); }}
    h1 {{ margin: 0 0 8px; font-size: 34px; }}
    p {{ color: var(--muted); line-height: 1.6; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
    }}
    .card h2 {{
      margin: 0 0 10px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      font-family: var(--mono);
    }}
    .metric {{
      font-family: var(--mono);
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 24px;
    }}
    a {{
      color: var(--text);
      text-decoration: none;
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 10px 14px;
      border-radius: 10px;
      font-family: var(--mono);
      font-size: 12px;
    }}
    a.primary {{
      border-color: rgba(61,214,198,0.35);
      background: linear-gradient(135deg, rgba(61,214,198,0.18), rgba(110,168,255,0.12));
    }}
    ul {{ color: var(--muted); line-height: 1.8; }}
    code {{
      font-family: var(--mono);
      background: rgba(255,255,255,0.04);
      padding: 2px 6px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">SCALE<span>X</span>AI</div>
    <h1>Load Test Console</h1>
    <p>
      This custom Locust page keeps the built-in Locust statistics UI, while adding a
      project-specific view for ScalexAI. Start the test from the default Locust UI,
      then watch live gateway metrics here.
    </p>

    <div class="grid">
      <div class="card">
        <h2>Target host</h2>
        <div class="metric">{host}</div>
        <div>Gateway API under test</div>
      </div>
      <div class="card">
        <h2>Traffic mix</h2>
        <ul>
          <li><code>fast</code> — weight 3 → tool_a</li>
          <li><code>slow</code> — weight 2 → tool_b</li>
          <li><code>flaky</code> — weight 1 → tool_c</li>
        </ul>
      </div>
      <div class="card">
        <h2>Failure rules</h2>
        <ul>
          <li>HTTP errors count as failures</li>
          <li><code>status: timeout</code> counts as failure</li>
          <li><code>status: failed</code> counts as failure</li>
        </ul>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Live gateway RPS</h2>
        <div class="metric" id="rps">—</div>
      </div>
      <div class="card">
        <h2>Live queue depth</h2>
        <div class="metric" id="queue">—</div>
      </div>
      <div class="card">
        <h2>Live error rate</h2>
        <div class="metric" id="err">—</div>
      </div>
    </div>

    <div class="links">
      <a class="primary" href="/">Back to Locust stats</a>
      <a href="{host}" target="_blank" rel="noreferrer">Open gateway dashboard</a>
      <a href="{host}/api/metrics" target="_blank" rel="noreferrer">Open raw metrics JSON</a>
    </div>
  </div>

  <script>
    async function refresh() {{
      try {{
        const res = await fetch("{host}/api/metrics");
        const m = await res.json();
        document.getElementById("rps").textContent = m.rps_last_10s;
        document.getElementById("queue").textContent = m.queue_depth;
        document.getElementById("err").textContent = m.error_rate_pct + "%";
      }} catch (e) {{
        document.getElementById("rps").textContent = "offline";
        document.getElementById("queue").textContent = "offline";
        document.getElementById("err").textContent = "offline";
      }}
    }}
    refresh();
    setInterval(refresh, 2000);
  </script>
</body>
</html>"""
