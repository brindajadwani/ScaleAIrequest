CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,
    task_type TEXT,
    routed_to TEXT,
    status TEXT,
    latency_ms INTEGER,
    queue_wait_ms INTEGER,
    created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests (created_at);
CREATE INDEX IF NOT EXISTS idx_requests_routed_to ON requests (routed_to);
