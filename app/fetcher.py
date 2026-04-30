import requests
import logging

logger = logging.getLogger(__name__)

FEDERAL_REGISTER_URL = "https://www.federalregister.gov/api/v1/documents.json"


def fetch_recent_documents(per_page: int = 20, interests: list[str] | None = None, conditions: dict | None = None) -> list[dict]:
    params = {
        "per_page": per_page,
        "order": "newest",
        "fields[]": ["document_number", "title", "abstract", "publication_date", "type", "agencies"],
    }
    if interests:
        params["conditions[term]"] = " ".join(interests)
    if conditions:
        for key, value in conditions.items():
            params[key] = value

    try:
        response = requests.get(FEDERAL_REGISTER_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        documents = data.get("results", [])
        logger.info(f"Fetched {len(documents)} documents from Federal Register")
        return [_normalize(doc) for doc in documents]
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        return []


def _normalize(doc: dict) -> dict:
    agencies = doc.get("agencies", [])
    agency_names = [a.get("name", "") for a in agencies if isinstance(a, dict)]
    return {
        "id": doc.get("document_number", ""),
        "title": doc.get("title", ""),
        "abstract": doc.get("abstract") or "",
        "published_date": doc.get("publication_date", ""),
        "source": "federal_register",
        "type": doc.get("type", ""),
        "agencies": agency_names,
    }
