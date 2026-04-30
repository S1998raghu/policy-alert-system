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

## Context Manager (`with` statement)

### What it is
A pattern that guarantees cleanup code runs — even if an exception is thrown.

```python
# without context manager — conn.close() skipped if exception
conn = get_connection()
row = conn.execute(...)   # crashes here
conn.close()              # never runs → connection leak

# with context manager — always cleans up
with get_connection() as conn:
    row = conn.execute(...)   # crashes here
# conn.close() runs automatically no matter what
```

### Why it matters
- No resource leaks — connections, files, locks always get released
- No manual cleanup — you can't forget it
- Handles exceptions correctly — rollbacks happen automatically on failure

### SQLite context manager specifically
```python
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("INSERT ...")
# automatically commits on success, rolls back on exception, closes connection
```

### async version with aiosqlite
```python
async with aiosqlite.connect(DB_PATH) as conn:
    await conn.execute("INSERT ...")
    await conn.commit()
```
Same pattern, but non-blocking — event loop can handle other requests while waiting for DB.

---

## SQLite → aiosqlite (async DB)

### Why we upgraded
SQLite is synchronous — calling `db.save_result()` inside an async function blocks the event loop. Every other request has to wait while the DB write finishes.

`aiosqlite` wraps SQLite with async/await so DB calls don't block:

```python
# before — blocks event loop
def save_result(...):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT ...")

# after — non-blocking
async def save_result(...):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("INSERT ...")
        await conn.commit()
```

### The async chain rule
When a function becomes `async def`, every caller must also `await` it and be `async def` itself. Async spreads upward through the call stack:

```
db.save_result()     → async def
  agent._process()   → already async, add await
    agent.run()      → already async, add await
      main.run_pipeline() → already async, add await
```

### WAL mode
```python
conn.execute("PRAGMA journal_mode=WAL")
```
WAL (Write-Ahead Logging) allows concurrent reads while a write is happening. Important when `asyncio.gather` fires 20 tasks that all hit the DB simultaneously.

---

## JSON Parsing — `json.loads()` vs safer alternatives

### The problem with `json.loads()`
```python
data = json.loads(raw)  # loads entire payload into memory at once
```
- No size limit — will parse a 1GB string without complaint
- Must have complete string before parsing starts — no streaming
- Two steps: parse then validate separately

### For small known payloads (LLM responses) — use Pydantic
```python
# before — two steps, no type safety
data = json.loads(raw)
return RelevanceAndScore(**data)

# after — one step, validates types automatically
return RelevanceAndScore.model_validate_json(raw)
```
`model_validate_json` parses and validates in one step. If the JSON is missing a field or has the wrong type, it raises a clear error immediately.

### For large/unknown payloads — use `ijson` (streaming parser)
```python
import ijson

# instead of loading entire file into memory:
with open("large_file.json", "rb") as f:
    for item in ijson.items(f, "results.item"):
        process(item)  # processes one item at a time
```
`ijson` reads the file as a stream — memory usage stays flat no matter how large the file is.

### When to use what

| Situation | Use |
|---|---|
| Small LLM response, known structure | `model_validate_json()` |
| Small payload, no Pydantic model | `json.loads()` is fine |
| Large file (logs, bulk API response) | `ijson` streaming |
| Untrusted external input | Size check + `model_validate_json()` |

---

## SRE Fixes

### 1. Retry with exponential backoff (tenacity)

**Problem:** 429 rate limit errors silently returned `importance_score=0`, permanently storing wrong IGNORE decisions in the DB.

**Fix:** `tenacity` library retries automatically on specific errors:
```python
@retry(
    retry=retry_if_exception_type(anthropic.RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def assess_document(...):
```

- `wait_exponential` — waits 2s, then 4s, then 8s... up to 30s max between retries
- `stop_after_attempt(3)` — gives up after 3 tries
- `retry_if_exception_type` — only retries on rate limits, not on your own bugs
- `reraise=True` — after all retries fail, raises the original exception so the caller knows

**Why exponential backoff vs fixed interval:**
Fixed: retry every 2s → hammers the API → makes rate limiting worse
Exponential: wait longer each time → gives the API time to recover

---

### 2. Timeouts on external calls

**Problem:** If Anthropic's API stalls, `/run` hangs forever — holds a connection open indefinitely.

**Fix:** Set timeout on the client:
```python
client = anthropic.AsyncAnthropic(
    api_key=...,
    timeout=30.0,  # raises APITimeoutError if no response in 30s
)
```

**Rule of thumb:** timeout = (p99 latency) × 6. Your p99 was ~5s → 30s timeout.

Always set timeouts on:
- HTTP clients (`requests`, `httpx`)
- LLM clients
- DB connections

---

### 3. Correlation IDs

**Problem:** 20 concurrent LLM calls produce interleaved logs with no way to tie errors to requests.

**Fix:** `contextvars.ContextVar` — a request-scoped variable safe for async:
```python
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# in middleware — set once per request
req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
request_id_var.set(req_id)

# anywhere in the call stack — read without passing it explicitly
rid = request_id_var.get()
logger.info(f"[{rid}] processing doc...")
```

`ContextVar` is like a thread-local variable but for async — each concurrent request gets its own value. Safe, no shared state.

The ID is also returned in the response header `X-Request-ID` so callers can trace their request through your logs.

---

### 4. Specific exception handling (never bare `except Exception`)

**Problem:** A bug in your own code gets swallowed the same way as a network error. You'd never know the difference.

**Rule:**
- **Expected failures** (network timeout, rate limit, API error) → catch specifically, log, return safe fallback
- **Unexpected failures** (bug in your code) → log at `critical` with `exc_info=True`, then `raise`

```python
except anthropic.RateLimitError:
    logger.error("rate limit exceeded")
    return safe_fallback()          # expected — keep going

except anthropic.APITimeoutError:
    logger.error("timed out")
    return safe_fallback()          # expected — keep going

except Exception as e:
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise                           # YOUR bug — crash loudly, return 500
```

`exc_info=True` prints the full stack trace in logs.
`raise` lets FastAPI return a 500 → Prometheus tracks it → alerts fire.

**For HTTP clients, split by error type:**
```python
except requests.Timeout:       # slow API
except requests.HTTPError:     # 4xx/5xx response
except requests.RequestException:  # network failure
```

Each tells you something different about what broke.

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
