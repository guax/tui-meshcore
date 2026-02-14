"""SQLite persistence for messages, contacts, and channels."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL    NOT NULL,
    sender_id   TEXT,
    sender_name TEXT,
    channel_id  TEXT,
    content     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'received',
    is_dm       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT    UNIQUE NOT NULL,
    name        TEXT,
    public_key  TEXT,
    last_seen   REAL,
    rssi        INTEGER,
    snr         REAL
);

CREATE TABLE IF NOT EXISTS channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    UNIQUE NOT NULL,
    secret      TEXT,
    is_private  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class DatabaseManager:
    """Thin wrapper around SQLite for chat history and node data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # --- lifecycle ---------------------------------------------------------

    def open(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._apply_schema()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _apply_schema(self) -> None:
        assert self._conn
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        self._conn.commit()

    # --- messages ----------------------------------------------------------

    def add_message(
        self,
        content: str,
        *,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        status: str = "received",
        is_dm: bool = False,
        timestamp: Optional[float] = None,
    ) -> int:
        assert self._conn
        ts = timestamp or time.time()
        cur = self._conn.execute(
            "INSERT INTO messages (timestamp, sender_id, sender_name, channel_id, content, status, is_dm) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, sender_id, sender_name, channel_id, content, status, int(is_dm)),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_messages(
        self,
        channel_id: Optional[str] = None,
        *,
        is_dm: bool = False,
        contact_id: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        assert self._conn
        if is_dm and contact_id:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE is_dm = 1 AND (sender_id = ? OR channel_id = ?) "
                "ORDER BY timestamp DESC LIMIT ?",
                (contact_id, contact_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE channel_id = ? AND is_dm = 0 "
                "ORDER BY timestamp DESC LIMIT ?",
                (channel_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # --- contacts ----------------------------------------------------------

    def upsert_contact(
        self,
        node_id: str,
        *,
        name: Optional[str] = None,
        public_key: Optional[str] = None,
        rssi: Optional[int] = None,
        snr: Optional[float] = None,
    ) -> None:
        assert self._conn
        self._conn.execute(
            "INSERT INTO contacts (node_id, name, public_key, last_seen, rssi, snr) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(node_id) DO UPDATE SET "
            "name = COALESCE(excluded.name, name), "
            "public_key = COALESCE(excluded.public_key, public_key), "
            "last_seen = excluded.last_seen, "
            "rssi = COALESCE(excluded.rssi, rssi), "
            "snr = COALESCE(excluded.snr, snr)",
            (node_id, name, public_key, time.time(), rssi, snr),
        )
        self._conn.commit()

    def get_contacts(self) -> list[dict[str, Any]]:
        assert self._conn
        rows = self._conn.execute(
            "SELECT * FROM contacts ORDER BY last_seen DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_contact_by_id(self, node_id: str) -> Optional[dict[str, Any]]:
        assert self._conn
        row = self._conn.execute(
            "SELECT * FROM contacts WHERE node_id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    # --- channels ----------------------------------------------------------

    def add_channel(self, name: str, *, secret: Optional[str] = None, is_private: bool = False) -> None:
        assert self._conn
        self._conn.execute(
            "INSERT OR IGNORE INTO channels (name, secret, is_private) VALUES (?, ?, ?)",
            (name, secret, int(is_private)),
        )
        self._conn.commit()

    def get_channels(self) -> list[dict[str, Any]]:
        assert self._conn
        rows = self._conn.execute("SELECT * FROM channels ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def remove_channel(self, name: str) -> None:
        assert self._conn
        self._conn.execute("DELETE FROM channels WHERE name = ?", (name,))
        self._conn.commit()
