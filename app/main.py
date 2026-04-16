import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import db
from app.agent import PolicyAgent

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Policy Change Alerting System",
    description="AI-powered regulatory monitoring. Ingests Federal Register documents, assesses relevance using an LLM, and generates personalized alerts based on user interest profiles.",
    version="1.0.0",
    lifespan=lifespan,
)

class UserProfile(BaseModel):
    user: str
    interests: list[str]
    alert_threshold: float


class RunRequest(BaseModel):
    user: str
    per_page: int = 20


@app.post("/user", responses={200: {"description": "User created or updated"}})
def create_or_update_user(profile: UserProfile):
    """
    Create or update a user profile.

    - **user**: unique username
    - **interests**: list of topics to monitor e.g. ["AI in healthcare", "data privacy"]
    - **alert_threshold**: importance score cutoff (0-10). Documents scoring at or above this trigger an ALERT.
    """
    db.upsert_user(profile.user, profile.interests, profile.alert_threshold)
    return {"status": "ok", "user": profile.user}


@app.post("/run", responses={200: {"description": "Pipeline results"}})
def run_pipeline(request: RunRequest):
    """
    Fetch the latest documents from the Federal Register and run the full agent pipeline for a user.

    - Fetches `per_page` documents (default 20)
    - Each document is assessed by the LLM for relevance and importance
    - Decision is made: ALERT / DAILY_DIGEST / IGNORE
    - All results are saved to the database

    Returns a summary count and the full list of results.
    """
    user_profile = db.get_user(request.user)
    if user_profile is None:
        raise HTTPException(status_code=404, detail=f"User '{request.user}' not found")

    agent = PolicyAgent(user_profile)
    results = agent.run(per_page=request.per_page)

    summary = {
        "total": len(results),
        "ALERT": sum(1 for r in results if r["decision"] == "ALERT"),
        "DAILY_DIGEST": sum(1 for r in results if r["decision"] == "DAILY_DIGEST"),
        "IGNORE": sum(1 for r in results if r["decision"] == "IGNORE"),
    }
    return {"user": request.user, "summary": summary, "results": results}


@app.get("/alerts", responses={200: {"description": "ALERT-level results for the user"}})
def get_alerts(user: str):
    """
    Return all ALERT-level results for a user, ordered most recent first.

    Only documents that scored at or above the user's alert_threshold appear here.
    """
    user_profile = db.get_user(user)
    if user_profile is None:
        raise HTTPException(status_code=404, detail=f"User '{user}' not found")

    alerts = db.get_alerts(user)
    return {"user": user, "alerts": alerts}


@app.get("/explain", responses={200: {"description": "Full reasoning for a document decision"}})
def explain(user: str, document_id: str):
    """
    Return the full reasoning for a specific document decision.

    - **user**: the username
    - **document_id**: the Federal Register document number e.g. 2026-07335

    Returns the LLM's relevance assessment, importance score, decision, and explanation.
    """
    result = db.get_result(user, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No result found for this user and document")
    return result
