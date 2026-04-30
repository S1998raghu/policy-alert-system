import logging
import os
import time
import anthropic
from dotenv import load_dotenv
load_dotenv()
from pydantic import BaseModel
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from app.metrics import LLM_CALL_LATENCY, LLM_FAILURES

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


class RelevanceAndScore(BaseModel):
    relevant: bool
    matched_interests: list[str]
    importance_score: float
    reasoning: str


@retry(
    retry=retry_if_exception_type(anthropic.RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def assess_document(document: dict, interests: list[str]) -> RelevanceAndScore:
    prompt = f"""You are a policy analyst assistant. Assess the following government document
for a user with these interests: {interests}

Document title: {document.get('title', '')}
Document abstract: {document.get('abstract', '')}
Published: {document.get('published_date', '')}
Agency: {', '.join(document.get('agencies', []))}

Return a JSON object with exactly these fields:
- relevant (bool): is this document relevant to the user's interests?
- matched_interests (list of strings): which specific interests from the list match this document
- importance_score (float between 0 and 10): how important is this document for the user?
- reasoning (string): one sentence explaining your decision

Only return valid JSON. No extra text."""

    t0 = time.perf_counter()
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        LLM_CALL_LATENCY.observe(time.perf_counter() - t0)
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return RelevanceAndScore.model_validate_json(raw)

    except Exception as e:
        LLM_FAILURES.inc()
        logger.error(f"LLM assessment failed: {e}")
        return RelevanceAndScore(
            relevant=False,
            matched_interests=[],
            importance_score=0.0,
            reasoning=f"LLM call failed: {e}",
        )
