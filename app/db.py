import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "policy_alerts.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user TEXT PRIMARY KEY,
            interests TEXT NOT NULL,
            alert_threshold REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            published_date TEXT,
            source TEXT,
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            document_id TEXT NOT NULL,
            summary TEXT,
            relevant INTEGER,
            matched_interests TEXT,
            importance_score REAL,
            decision TEXT,
            explanation TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user) REFERENCES users(user),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
    """)
    conn.commit()
    conn.close()


def upsert_user(user: str, interests: list[str], alert_threshold: float):
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (user, interests, alert_threshold) VALUES (?, ?, ?) "
        "ON CONFLICT(user) DO UPDATE SET interests=excluded.interests, alert_threshold=excluded.alert_threshold",
        (user, json.dumps(interests), alert_threshold),
    )
    conn.commit()
    conn.close()


def get_user(user: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE user = ?", (user,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {"user": row["user"], "interests": json.loads(row["interests"]), "alert_threshold": row["alert_threshold"]}


def upsert_document(doc: dict):
    conn = get_connection()
    conn.execute(
        "INSERT INTO documents (id, title, abstract, published_date, source, raw_json) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO NOTHING",
        (doc["id"], doc.get("title"), doc.get("abstract"), doc.get("published_date"), doc.get("source"), json.dumps(doc)),
    )
    conn.commit()
    conn.close()


def save_result(user: str, document_id: str, result: dict):
    conn = get_connection()
    conn.execute(
        "INSERT INTO results (user, document_id, summary, relevant, matched_interests, importance_score, decision, explanation) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user,
            document_id,
            result.get("summary"),
            int(result.get("relevant", False)),
            json.dumps(result.get("matched_interests", [])),
            result.get("importance_score"),
            result.get("decision"),
            result.get("explanation"),
        ),
    )
    conn.commit()
    conn.close()


def get_alerts(user: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT r.*, d.title FROM results r JOIN documents d ON r.document_id = d.id "
        "WHERE r.user = ? AND r.decision = 'ALERT' ORDER BY r.created_at DESC",
        (user,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_result(user: str, document_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM results WHERE user = ? AND document_id = ?",
        (user, document_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
