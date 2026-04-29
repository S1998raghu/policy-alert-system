# Policy Change Alerting System

An AI-powered regulatory monitoring system that ingests documents from the Federal Register, evaluates them against user interest profiles using Claude (Anthropic), and generates personalized alerts with explainable decisions.

## How it works

Each document passes through a multi-step agent pipeline:

1. **Fetch** — pull latest documents from the Federal Register API
2. **Summarize** — LLM generates a concise summary
3. **Relevance** — LLM classifies relevance against the user's interest topics
4. **Score** — importance scored 0–10 based on relevance, domain, regulatory level, and recency
5. **Decide** — `ALERT` / `DAILY_DIGEST` / `IGNORE` based on score vs. user threshold
6. **Explain** — LLM produces a plain-language rationale for the decision

## Setup

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Local (without Docker)

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

### Docker Compose (includes Prometheus + Grafana)

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
docker compose up --build
```

| Service    | URL                    |
|------------|------------------------|
| API        | http://localhost:8000  |
| Prometheus | http://localhost:9090  |
| Grafana    | http://localhost:3000  |

Grafana default credentials: `admin` / `admin`

## API

Interactive docs available at `http://localhost:8000/docs`.

### `POST /user` — create or update a user profile

```json
{
  "user": "healthcare_analyst",
  "interests": ["AI in healthcare", "data privacy"],
  "alert_threshold": 7
}
```

### `POST /run` — fetch documents and run the agent pipeline

```json
{
  "user": "healthcare_analyst",
  "per_page": 20
}
```

Returns a summary count and full result list including decision and explanation for each document.

### `GET /alerts?user=<username>` — retrieve ALERT-level results

Returns documents that scored at or above the user's `alert_threshold`.

### `GET /explain?user=<username>&document_id=<id>` — full reasoning for a document

Example document ID: `2026-07335`

### `GET /health` — liveness check

### `GET /metrics` — Prometheus metrics

## Example output

```json
{
  "summary": "New federal regulation on AI in healthcare systems",
  "relevance": {
    "relevant": true,
    "matched_interests": ["AI in healthcare"]
  },
  "importance_score": 8,
  "decision": "ALERT",
  "explanation": "High relevance to monitored interests and federal-level regulatory impact."
}
```

## Decision logic

| Condition                          | Decision       |
|------------------------------------|----------------|
| score ≥ threshold                  | `ALERT`        |
| score ≥ threshold − 2              | `DAILY_DIGEST` |
| score < threshold − 2              | `IGNORE`       |

## Project structure

```
policy-alert-system/
├── app/
│   ├── main.py       # FastAPI entrypoint + routes
│   ├── agent.py      # PolicyAgent — orchestrates the pipeline
│   ├── fetcher.py    # Federal Register data ingestion
│   ├── decision.py   # Decision engine
│   ├── llm.py        # Anthropic Claude calls
│   ├── metrics.py    # Prometheus instrumentation
│   └── db.py         # SQLite database layer
├── infra/            # Prometheus + Grafana config
├── k8s/              # Kubernetes manifests
├── tests/
├── docker-compose.yml
└── requirements.txt
```

## Running on GitHub

### 1. Add your API key as a secret

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | your Anthropic API key |

This is the only secret required. `GITHUB_TOKEN` is provided automatically by GitHub.

### 2. CI runs automatically

Every push to `main` and every pull request triggers `.github/workflows/ci.yml`, which:

1. Lints the code with `ruff`
2. Runs `pytest` (using your `ANTHROPIC_API_KEY` secret)
3. Builds the Docker image and pushes it to **GitHub Container Registry (GHCR)** at:
   ```
   ghcr.io/<your-github-username>/<repo-name>:latest
   ```
   The push only happens on merges to `main`, not on PRs.

### 3. Pull and run the published image

Once CI has pushed an image you can run it anywhere Docker is available:

```bash
docker pull ghcr.io/<your-github-username>/<repo-name>:latest
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your-key \
  ghcr.io/<your-github-username>/<repo-name>:latest
```

### 4. Make the image public (optional)

By default GHCR packages are private. To make the image publicly pullable:

Go to your repo → **Packages** → select the package → **Package settings → Change visibility → Public**

---

## Tech stack

- **FastAPI** — API layer
- **Anthropic Claude** — LLM for summarization, relevance, and explanation
- **SQLite** — document and result storage
- **Prometheus + Grafana** — observability
- **Docker / Kubernetes** — deployment
