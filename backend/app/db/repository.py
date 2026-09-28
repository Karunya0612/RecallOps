"""SQLite Data Access Layer for RecallOps incidents."""

from datetime import datetime, timezone
import sqlite3
from typing import Any, Optional
import uuid
from fastapi import Depends

from app.core.config import Settings, get_settings


class IncidentRepository:
    """Repository handling local persistence for incidents in SQLite."""

    def __init__(
        self,
        db_path: str = "recallops.db",
        connection: Optional[sqlite3.Connection] = None,
    ) -> None:
        self.db_path = db_path
        if connection is not None:
            self._conn = connection
        else:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create incidents table and indexes if they do not exist."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    affected_service TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    logs TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                );
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incidents_created_at 
                ON incidents(created_at DESC);
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_outcomes (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    resolution_attempted TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    engineer_notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents (id)
                );
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incident_outcomes_incident_id 
                ON incident_outcomes(incident_id);
                """
            )

    def create_incident(
        self,
        title: str,
        description: str,
        affected_service: str,
        severity: str,
        logs: Optional[str] = None,
        status: str = "open",
        incident_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> dict[str, Any]:
        """Insert a new incident record into SQLite."""
        inc_id = incident_id or f"inc-{uuid.uuid4().hex[:12]}"
        now_utc = created_at or datetime.now(timezone.utc).isoformat()

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO incidents (
                    id, title, description, affected_service, severity, logs, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL);
                """,
                (inc_id, title, description, affected_service, severity, logs, status, now_utc),
            )

        return {
            "id": inc_id,
            "title": title,
            "description": description,
            "affected_service": affected_service,
            "severity": severity,
            "logs": logs,
            "status": status,
            "created_at": now_utc,
            "updated_at": None,
        }

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Retrieve an incident by unique identifier."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, affected_service, severity, logs, status, created_at, updated_at
            FROM incidents
            WHERE id = ?;
            """,
            (incident_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_incidents(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retrieve paginated incidents ordered by creation time descending."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM incidents;")
        count_row = cursor.fetchone()
        total_count = count_row[0] if count_row else 0

        cursor.execute(
            """
            SELECT id, title, description, affected_service, severity, logs, status, created_at, updated_at
            FROM incidents
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows], total_count

    def record_outcome(
        self,
        incident_id: str,
        resolution_attempted: str,
        outcome: str,
        engineer_notes: Optional[str] = None,
        outcome_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record an engineer-confirmed outcome in SQLite."""
        out_id = outcome_id or f"out-{uuid.uuid4().hex[:12]}"
        now_utc = created_at or datetime.now(timezone.utc).isoformat()

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO incident_outcomes (
                    id, incident_id, resolution_attempted, outcome, engineer_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (out_id, incident_id, resolution_attempted, outcome, engineer_notes, now_utc),
            )

        return {
            "id": out_id,
            "incident_id": incident_id,
            "resolution_attempted": resolution_attempted,
            "outcome": outcome,
            "engineer_notes": engineer_notes,
            "created_at": now_utc,
        }

    def get_outcome(self, outcome_id: str) -> Optional[dict[str, Any]]:
        """Retrieve an outcome record by ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, incident_id, resolution_attempted, outcome, engineer_notes, created_at
            FROM incident_outcomes
            WHERE id = ?;
            """,
            (outcome_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_outcomes_for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        """Retrieve all outcome records for a specific incident."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, incident_id, resolution_attempted, outcome, engineer_notes, created_at
            FROM incident_outcomes
            WHERE incident_id = ?
            ORDER BY created_at DESC;
            """,
            (incident_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def delete_outcome(self, outcome_id: str) -> bool:
        """Delete an outcome record (used for rollbacks if external memory retention fails)."""
        with self._conn:
            cursor = self._conn.execute(
                "DELETE FROM incident_outcomes WHERE id = ?;",
                (outcome_id,),
            )
            return cursor.rowcount > 0

    def close(self) -> None:
        """Close SQLite database connection."""
        if self._conn is not None:
            self._conn.close()


def get_incident_repository(
    settings: Settings = Depends(get_settings),
) -> IncidentRepository:
    """FastAPI dependency for accessing the incident repository."""
    return IncidentRepository(db_path=settings.sqlite_db_path)
