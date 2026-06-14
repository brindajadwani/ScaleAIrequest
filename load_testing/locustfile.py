from locust import HttpUser, task, between


class APIUser(HttpUser):
    """
    Simulates clients hitting the ScalexAI gateway.

    Run with:
        locust -f load_testing/locustfile.py --host http://localhost:8000

    Then open http://localhost:8089 to set number of users and spawn rate.
    """

    wait_time = between(0.1, 0.5)

    @task(3)
    def fast_task(self):
        self.client.post("/api/task", json={"task_type": "fast"})

    @task(2)
    def slow_task(self):
        self.client.post("/api/task", json={"task_type": "slow"})

    @task(1)
    def flaky_task(self):
        self.client.post("/api/task", json={"task_type": "flaky"})
