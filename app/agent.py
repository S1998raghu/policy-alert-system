import logging
from app.fetcher import fetch_recent_documents
from app.llm import assess_document
from app.decision import make_decision

from app import db

logger = logging.getLogger(__name__)


class PolicyAgent:
    def __init__(self, user_profile: dict):
        self.user = user_profile["user"]
        self.interests = user_profile["interests"]
        self.alert_threshold = user_profile["alert_threshold"]

    def run(self, per_page: int = 20) -> list[dict]:
        logger.info(f"[{self.user}] Fetching documents...")
        documents = fetch_recent_documents(per_page=per_page)

        results = []
        for doc in documents:
            db.upsert_document(doc)
            result = self._process(doc)
            db.save_result(self.user, doc["id"], result)
            results.append(result)
            logger.info(f"[{self.user}] {doc['id']} → {result['decision']} (score={result['importance_score']})")

        return results

    def _process(self, document: dict) -> dict:
        # Step 1: Summarize
      

        # Step 2: LLM assesses relevance + importance together
        assessment = assess_document(document, self.interests)

        # Step 3: Make decision based on LLM score
        decision = make_decision(assessment.importance_score, self.alert_threshold)

        # Step 4: Generate explanation
       

        return {
            "document_id": document["id"],
            
            "relevant": assessment.relevant,
            "matched_interests": assessment.matched_interests,
            "importance_score": assessment.importance_score,
            "decision": decision,
            "reasoning": assessment.reasoning,
        }
