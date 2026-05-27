from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import now_iso


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._memory_conn: sqlite3.Connection | None = None
        if str(path) == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @classmethod
    def from_root(cls, root: Path, override: str | Path | None = None) -> "Database":
        configured = override or os.getenv("TCM_DB_PATH")
        return cls(configured or root / "data" / "tcm_diagnosis.sqlite3")

    def save_session(self, session_id: str, session: Any) -> None:
        profile = getattr(session, "profile", {}) or {}
        baseline = getattr(session, "baseline_snapshot", {}) or {}
        user_id = str(getattr(session, "user_id", "") or profile.get("user_id") or "")
        if profile:
            self.save_profile(profile)
        if baseline:
            self.save_baseline(baseline, user_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO diagnosis_sessions (
                    session_id, user_id, user_type, mode, current_step, status,
                    profile_json, baseline_json, face_observation_json,
                    chief_complaint_json, ten_questions_json, symptoms_json,
                    qa_history_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    user_type=excluded.user_type,
                    mode=excluded.mode,
                    current_step=excluded.current_step,
                    status=excluded.status,
                    profile_json=excluded.profile_json,
                    baseline_json=excluded.baseline_json,
                    face_observation_json=excluded.face_observation_json,
                    chief_complaint_json=excluded.chief_complaint_json,
                    ten_questions_json=excluded.ten_questions_json,
                    symptoms_json=excluded.symptoms_json,
                    qa_history_json=excluded.qa_history_json,
                    updated_at=excluded.updated_at
                """,
                (
                    session_id,
                    user_id,
                    getattr(session, "user_type", ""),
                    getattr(session, "mode", ""),
                    getattr(session, "current_step", ""),
                    getattr(session, "status", ""),
                    _json(profile),
                    _json(baseline),
                    _json(getattr(session, "face_observation", {}) or {}),
                    _json(getattr(session, "chief_complaint", {}) or {}),
                    _json(getattr(session, "ten_questions", []) or []),
                    _json(getattr(session, "symptoms", []) or []),
                    _json(getattr(session, "qa_history", []) or []),
                    now_iso(),
                    now_iso(),
                ),
            )

    def save_profile(self, profile: dict[str, Any]) -> None:
        user_id = str(profile.get("user_id") or "")
        if not user_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (
                    user_id, display_name, age, sex, height_cm, weight_kg,
                    lifestyle_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    age=excluded.age,
                    sex=excluded.sex,
                    height_cm=excluded.height_cm,
                    weight_kg=excluded.weight_kg,
                    lifestyle_json=excluded.lifestyle_json,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    profile.get("display_name", ""),
                    profile.get("age"),
                    profile.get("sex", "unspecified"),
                    profile.get("height_cm"),
                    profile.get("weight_kg"),
                    _json(profile.get("lifestyle", {})),
                    profile.get("created_at") or now_iso(),
                    now_iso(),
                ),
            )

    def save_baseline(self, baseline: dict[str, Any], user_id: str = "") -> None:
        owner_id = str(baseline.get("user_id") or user_id or "")
        if not owner_id:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO baselines (
                    user_id, baseline_id, baseline_days, status,
                    face_summary_json, symptom_baseline_json, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    baseline_id=excluded.baseline_id,
                    baseline_days=excluded.baseline_days,
                    status=excluded.status,
                    face_summary_json=excluded.face_summary_json,
                    symptom_baseline_json=excluded.symptom_baseline_json,
                    last_updated=excluded.last_updated
                """,
                (
                    owner_id,
                    baseline.get("baseline_id", ""),
                    int(baseline.get("baseline_days", 0) or 0),
                    baseline.get("status", "none"),
                    _json(baseline.get("face_summary", {})),
                    _json(baseline.get("symptom_baseline", {})),
                    baseline.get("last_updated") or now_iso(),
                ),
            )

    def save_result(self, session_id: str, payload: dict[str, Any], result: dict[str, Any]) -> str:
        user_id = str((payload.get("profile") or {}).get("user_id") or "")
        if not user_id:
            session_row = self.get_session(session_id)
            user_id = str(session_row.get("user_id", "") if session_row else "")
        top_patterns = [
            str(item.get("pattern"))
            for item in (result.get("possibilities") or [])[:3]
            if isinstance(item, dict) and item.get("pattern")
        ]
        result_id = uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO diagnosis_results (
                    result_id, session_id, user_id, result_json,
                    top_patterns_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (result_id, session_id, user_id, _json(result), _json(top_patterns), now_iso()),
            )
        return result_id

    def get_user_history(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT result_id, session_id, user_id, result_json, top_patterns_json, created_at
                FROM diagnosis_results
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [
            {
                "result_id": row["result_id"],
                "session_id": row["session_id"],
                "user_id": row["user_id"],
                "result": _loads(row["result_json"], {}),
                "top_patterns": _loads(row["top_patterns_json"], []),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM diagnosis_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                "profiles": conn.execute("SELECT COUNT(*) FROM user_profiles").fetchone()[0],
                "sessions": conn.execute("SELECT COUNT(*) FROM diagnosis_sessions").fetchone()[0],
                "results": conn.execute("SELECT COUNT(*) FROM diagnosis_results").fetchone()[0],
            }

    def _connect(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    age INTEGER,
                    sex TEXT,
                    height_cm REAL,
                    weight_kg REAL,
                    lifestyle_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS baselines (
                    user_id TEXT PRIMARY KEY,
                    baseline_id TEXT,
                    baseline_days INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'none',
                    face_summary_json TEXT NOT NULL DEFAULT '{}',
                    symptom_baseline_json TEXT NOT NULL DEFAULT '{}',
                    last_updated TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnosis_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    user_type TEXT,
                    mode TEXT,
                    current_step TEXT,
                    status TEXT,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    baseline_json TEXT NOT NULL DEFAULT '{}',
                    face_observation_json TEXT NOT NULL DEFAULT '{}',
                    chief_complaint_json TEXT NOT NULL DEFAULT '{}',
                    ten_questions_json TEXT NOT NULL DEFAULT '[]',
                    symptoms_json TEXT NOT NULL DEFAULT '[]',
                    qa_history_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnosis_results (
                    result_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    user_id TEXT,
                    result_json TEXT NOT NULL,
                    top_patterns_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_user_id
                    ON diagnosis_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_results_user_id_created
                    ON diagnosis_results(user_id, created_at DESC);
                """
            )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback
