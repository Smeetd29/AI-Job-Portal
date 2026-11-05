import os
try:
    from locust import HttpUser, task, between
except ImportError:
    HttpUser = object  # type: ignore

    def task(weight=1):
        return lambda f: f

    def between(a, b):
        return 1

class CareerConnectLoadUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Optional: authenticate if JWT or session token is available
        self.auth_token = os.environ.get("LOAD_TEST_AUTH_TOKEN", "")
        self.headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}

    @task(4)
    def test_job_list(self):
        """Standard browse query with filters."""
        self.client.get("/jobs/?category=Engineering&is_active=true", name="[GET] /jobs/")

    @task(3)
    def test_health_probes(self):
        """Liveness and readiness checks."""
        self.client.get("/healthz", name="[GET] /healthz")
        self.client.get("/readyz", name="[GET] /readyz")

    @task(2)
    def test_recommendations(self):
        """AI recommendations query (cached in Redis)."""
        self.client.get("/api/ai/recommendations/?min_match=50", headers=self.headers, name="[GET] /api/ai/recommendations/")

    @task(1)
    def test_autofill_endpoint(self):
        """Resume parsing and form autofill."""
        payload = {"resume_text": "Alex Smith\nSummary: Senior Python dev with 6 years experience.\nSkills: Python, Django, PostgreSQL\nEducation: BS CS"}
        self.client.post("/api/ai/autofill/", json=payload, headers=self.headers, name="[POST] /api/ai/autofill/")
