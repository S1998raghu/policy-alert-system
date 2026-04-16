import json
import logging
from openai import OpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)


class RelevanceAndScore(BaseModel):
    relevant: bool
    matched_interests: list[str]
    importance_score: float
    reasoning: str


def assess_document(document: dict, interests: list[str]) -> RelevanceAndScore:
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

    try:
        response = client.chat.completions.create(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()

        # strip markdown code fences if model wraps response
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)
        return RelevanceAndScore(**data)

    except Exception as e:
        logger.error(f"LLM assessment failed: {e}")
        # fallback to safe defaults so pipeline doesn't crash
        return RelevanceAndScore(
            relevant=False,
            matched_interests=[],
            importance_score=0.0,
            reasoning=f"LLM call failed: {e}",
        )
