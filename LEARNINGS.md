# Learnings

## Async / Await

### What async actually means
- `async def` alone does nothing — it just means the function *can* be paused
- `await` pauses the current function and lets other requests run while waiting
- `await` inside a `for` loop is still sequential — each item waits for the previous one
- `asyncio.gather()` is what actually runs things concurrently

### The difference
```python
# sequential — still slow even with await
for doc in documents:
    result = await process(doc)  # waits for each one before starting next

# concurrent — all start at the same time
results = await asyncio.gather(*[process(doc) for doc in documents])
```

### What * means
`*` unpacks a list into individual arguments:
```python
tasks = [task1, task2, task3]
asyncio.gather(*tasks)
# same as
asyncio.gather(task1, task2, task3)
```

### Measured result on this project
Refactored 20 sequential LLM calls to run concurrently using `asyncio.gather`.

| | Before (sync) | After (async gather) |
|---|---|---|
| Per `/run` call | ~23s | ~6s |
| Improvement | — | 4x faster |

Verified using Prometheus: `http_request_latency_seconds_sum{endpoint="/run"}`

---

## Middleware

### What it is
A function that intercepts every HTTP request before it hits the route handler. Runs automatically — you never call it manually.

### Pattern
```python
async def middleware(request, call_next):
    # before — request hasn't hit route yet
    t0 = time.perf_counter()

    response = await call_next(request)  # route runs here

    # after — route has finished
    elapsed = time.perf_counter() - t0
    print(f"took {elapsed:.2f}s")

    return response
```

### Key points
- `call_next` is injected by FastAPI — it represents everything after your middleware
- If you forget to call `call_next`, the request never reaches the route
- Great for: timing, logging, auth, rate limiting
- Avoid reading `response.body` in middleware — it consumes the stream

### Definition
> Middleware is a feature added to an existing workflow for a specific task, unrelated and isolated from the rest — it runs automatically on every request without the routes knowing about it.

---

## Prometheus / Metrics

### Two metric types used
- `Counter` — only goes up. Used for counts: requests, alerts, failures
- `Histogram` — records distribution of values. Used for latency with buckets

### How it works
```
Python code → increments Counter/Histogram in memory
→ GET /metrics → Prometheus scrapes every 15s
→ Grafana queries Prometheus → renders charts
```

Your app knows nothing about Prometheus. It just exposes `/metrics`. The `infra/` folder wires up the observers.

### prometheus_client vs instrumentator
- `prometheus_client` — you define and increment metrics manually (what this project uses)
- `prometheus-fastapi-instrumentator` — one-liner that auto-instruments all HTTP routes

Manual approach is better for portfolios — shows you understand what's being measured.

---

## FastAPI vs Flask

| | Flask | FastAPI |
|---|---|---|
| Async support | No (without extensions) | Yes, natively |
| Auto docs | No | Yes (`/docs`) |
| Input validation | Manual | Automatic via Pydantic |
| If you write sync code | Same | Same performance as Flask |

FastAPI gives you the tools. You still have to use them correctly.

---

## Design Patterns (seen in this codebase)

| Pattern | Where | What it does |
|---|---|---|
| Middleware | `main.py` | Intercepts every request |
| Pipeline | `agent.py` | fetch → score → decide → explain |
| Repository | `db.py` | All DB logic in one place |
| Decorator | `@app.get` | Registers routes without changing functions |
| Singleton | `metrics.py` | One Counter/Histogram instance shared everywhere |
| Observer | Prometheus | App exposes metrics, Prometheus watches |
