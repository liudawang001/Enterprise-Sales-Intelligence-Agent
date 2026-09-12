from __future__ import annotations

import os
from uuid import uuid4

from locust import HttpUser, between, task


class WorkspaceUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        token = os.getenv("LOADTEST_BEARER_TOKEN")
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.session_id = f"load-{uuid4()}"
        self.task_id = os.getenv("LOADTEST_TASK_ID", "")

    @task(5)
    def task_list(self) -> None:
        self.client.get("/api/tasks", name="GET /api/tasks")

    @task(4)
    def lead_page(self) -> None:
        if self.task_id:
            self.client.get(f"/api/tasks/{self.task_id}/versions/1/leads?page=1&page_size=20", name="GET lead page")

    @task(2)
    def business_qa(self) -> None:
        request_id = str(uuid4())
        self.client.post(
            "/api/chat",
            json={"session_id": self.session_id, "message": "集团V网业务适合哪些企业？", "request_id": request_id},
            headers={"X-Request-ID": request_id},
            name="POST business QA",
        )

    @task(1)
    def sse_connect(self) -> None:
        if self.task_id:
            with self.client.get(
                f"/api/tasks/{self.task_id}/events/stream", stream=True, name="GET SSE", timeout=5, catch_response=True
            ) as response:
                response.success() if response.status_code == 200 else response.failure(str(response.status_code))
