from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.database import connection, utc_now

logger = logging.getLogger(__name__)


class FirebaseMirror:
    def __init__(self, settings: Settings):
        self.enabled = settings.firebase_enabled
        self._app = None
        self._database = None
        if settings.firebase_database_url and not settings.firebase_credentials:
            raise ValueError("FIREBASE_CREDENTIALS is required when FIREBASE_DATABASE_URL is set")
        if settings.firebase_credentials and not settings.firebase_database_url:
            raise ValueError("FIREBASE_DATABASE_URL is required when FIREBASE_CREDENTIALS is set")
        if not self.enabled:
            return
        if not settings.firebase_credentials.is_file():
            raise FileNotFoundError(f"Firebase credential file not found: {settings.firebase_credentials}")
        import firebase_admin
        from firebase_admin import credentials, db

        try:
            self._app = firebase_admin.get_app("railway-crack-api")
        except ValueError:
            self._app = firebase_admin.initialize_app(
                credentials.Certificate(str(settings.firebase_credentials)),
                {"databaseURL": settings.firebase_database_url},
                name="railway-crack-api",
            )
        self._database = db

    def set(self, path: str, payload: dict) -> None:
        if not self.enabled:
            return
        self._database.reference(path, app=self._app).set(payload)


def _due_events(limit: int = 25) -> list[dict]:
    with connection() as conn:
        # Each outbox payload is a full Firebase value. Only the newest value
        # per path needs delivery; older failed writes must never overwrite it.
        conn.execute(
            """DELETE FROM sync_outbox WHERE outbox_id NOT IN (
                   SELECT MAX(outbox_id) FROM sync_outbox GROUP BY target_path
               )"""
        )
        rows = conn.execute(
            "SELECT * FROM sync_outbox WHERE next_attempt_at<=? ORDER BY outbox_id LIMIT ?",
            (utc_now(), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _delete_event(outbox_id: int) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM sync_outbox WHERE outbox_id=?", (outbox_id,))


def _retry_event(outbox_id: int, attempts: int, error: str) -> None:
    delay = min(3600, 2 ** min(attempts + 1, 11))
    next_attempt = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with connection() as conn:
        conn.execute(
            "UPDATE sync_outbox SET attempts=attempts+1,next_attempt_at=?,last_error=? WHERE outbox_id=?",
            (next_attempt, error[:1000], outbox_id),
        )


async def dispatch_outbox(mirror: FirebaseMirror, stop: asyncio.Event, interval_seconds: float = 2.0) -> None:
    while not stop.is_set():
        events = await asyncio.to_thread(_due_events)
        for event in events:
            try:
                payload = json.loads(event["payload_json"])
                await asyncio.to_thread(mirror.set, event["target_path"], payload)
                await asyncio.to_thread(_delete_event, event["outbox_id"])
            except Exception as exc:
                _retry_event(event["outbox_id"], event["attempts"], str(exc))
                logger.exception("Firebase mirror update failed for outbox id %s", event["outbox_id"])
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass

