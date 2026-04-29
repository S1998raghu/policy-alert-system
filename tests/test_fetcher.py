from unittest.mock import patch, MagicMock
from app.fetcher import fetch_recent_documents, _normalize


def test_normalize_basic():
    raw = {
        "document_number": "2026-001",
        "title": "Test Rule",
        "abstract": "An abstract.",
        "publication_date": "2026-01-01",
        "type": "Rule",
        "agencies": [{"name": "EPA"}, {"name": "FDA"}],
    }
    doc = _normalize(raw)
    assert doc["id"] == "2026-001"
    assert doc["title"] == "Test Rule"
    assert doc["agencies"] == ["EPA", "FDA"]
    assert doc["source"] == "federal_register"


def test_normalize_missing_fields():
    doc = _normalize({})
    assert doc["id"] == ""
    assert doc["abstract"] == ""
    assert doc["agencies"] == []


def test_fetch_returns_empty_on_error():
    with patch("app.fetcher.requests.get") as mock_get:
        mock_get.side_effect = Exception("network error")
        result = fetch_recent_documents()
    assert result == []


def test_fetch_parses_results():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "document_number": "2026-123",
                "title": "AI Regulation",
                "abstract": "Rules about AI.",
                "publication_date": "2026-04-01",
                "type": "Rule",
                "agencies": [{"name": "FTC"}],
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.fetcher.requests.get", return_value=mock_response):
        docs = fetch_recent_documents(per_page=1)

    assert len(docs) == 1
    assert docs[0]["id"] == "2026-123"
    assert docs[0]["agencies"] == ["FTC"]
