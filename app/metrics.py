from prometheus_client import Counter, Histogram

ALERTS_GENERATED = Counter("policy_alerts_generated_total", "ALERT-level documents generated")
PIPELINE_RUNS = Counter("policy_pipeline_runs_total", "Total /run pipeline invocations")
LLM_CALL_LATENCY = Histogram(
    "policy_llm_call_seconds",
    "LLM assess_document call latency",
    buckets=[0.5, 1, 2, 5, 10, 30],
)
LLM_FAILURES = Counter("policy_llm_failures_total", "Failed LLM calls")
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
HTTP_REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds", "HTTP request latency", ["endpoint"]
)
