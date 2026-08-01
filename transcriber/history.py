"""Local SQLite log of past dictations."""
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "history.db"


@dataclass
class HistoryEntry:
    id: int
    text: str
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )"""
    )
    return conn


def add_entry(text: str) -> None:
    if not text.strip():
        return
    with _connect() as conn:
        conn.execute("INSERT INTO history (text) VALUES (?)", (text,))


def get_entries(limit: int = 500) -> list[HistoryEntry]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, text, created_at FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [HistoryEntry(*row) for row in rows]


def delete_entry(entry_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))


def clear_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM history")
