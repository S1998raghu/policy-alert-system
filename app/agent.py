import asyncio
import logging
from app.fetcher import fetch_recent_documents
from app.llm import assess_document
from app.decision import make_decision
from app.main import request_id_var
from app import db

logger = logging.getLogger(__name__)


class PolicyAgent:
    def __init__(self, user_profile: dict):
        self.user = user_profile["user"]
        self.interests = user_profile["interests"]
        self.alert_threshold = user_profile["alert_threshold"]

    async def run(self, per_page: int = 20) -> list[dict]:
        rid = request_id_var.get()
        logger.info(f"[{rid}][{self.user}] Fetching documents...")
        documents = fetch_recent_documents(per_page=per_page, interests=self.interests)
        await asyncio.gather(*[db.upsert_document(doc) for doc in documents])
        results = await asyncio.gather(*[self._process(doc) for doc in documents])

        for doc, result in zip(documents, results):
            logger.info(f"[{rid}][{self.user}] {doc['id']} → {result['decision']} (score={result['importance_score']})")
        await asyncio.gather(*[db.save_result(self.user, doc["id"], result) for doc, result in zip(documents, results)])

        return results

    async def _process(self, document: dict) -> dict:
       
       
        
        # Step 1: LLM assesses relevance + importance together
        assessment = await assess_document(document, self.interests)

        # Step 2: Make decision based on LLM score
        decision = make_decision(assessment.importance_score, self.alert_threshold)

        result = {
            "document_id": document["id"],
            "relevant": assessment.relevant,
            "matched_interests": assessment.matched_interests,
            "importance_score": assessment.importance_score,
            "decision": decision,
            "reasoning": assessment.reasoning,
        }
      
        return result