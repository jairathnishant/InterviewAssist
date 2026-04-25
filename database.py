import sqlite3
import uuid
import json
from datetime import datetime
from typing import Optional

DB_PATH = "interviews.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS interviews (
                id                   TEXT PRIMARY KEY,
                token                TEXT UNIQUE NOT NULL,
                candidate_name       TEXT NOT NULL,
                role                 TEXT NOT NULL,
                role_desc            TEXT NOT NULL,
                experience_years     INTEGER NOT NULL,
                resume_text          TEXT NOT NULL DEFAULT '',
                api_key              TEXT NOT NULL DEFAULT '',
                status               TEXT NOT NULL DEFAULT 'ready',
                created_at           TEXT NOT NULL,
                recommendation       TEXT,
                overall_summary      TEXT,
                strengths            TEXT DEFAULT '[]',
                areas_for_improvement TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS questions (
                id                     TEXT PRIMARY KEY,
                interview_id           TEXT NOT NULL REFERENCES interviews(id),
                order_index            INTEGER NOT NULL,
                type                   TEXT NOT NULL,
                category               TEXT NOT NULL,
                text                   TEXT NOT NULL,
                expected_answer_points TEXT NOT NULL DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS answers (
                id                    TEXT PRIMARY KEY,
                interview_id          TEXT NOT NULL REFERENCES interviews(id),
                question_id           TEXT NOT NULL REFERENCES questions(id),
                order_index           INTEGER NOT NULL,
                answer_text           TEXT NOT NULL DEFAULT '',
                score                 REAL,
                feedback              TEXT,
                communication_clarity REAL
            );
        """)


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row else None


# ── Interviews ────────────────────────────────────────────────────────────────

def create_interview(
    candidate_name: str,
    role: str,
    role_desc: str,
    experience_years: int,
    resume_text: str,
    api_key: str,
) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "token": str(uuid.uuid4()),
        "candidate_name": candidate_name,
        "role": role,
        "role_desc": role_desc,
        "experience_years": experience_years,
        "resume_text": resume_text,
        "api_key": api_key,
        "status": "ready",
        "created_at": datetime.utcnow().isoformat(),
    }
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO interviews
               (id, token, candidate_name, role, role_desc, experience_years,
                resume_text, api_key, status, created_at)
               VALUES (:id, :token, :candidate_name, :role, :role_desc,
                       :experience_years, :resume_text, :api_key, :status, :created_at)""",
            row,
        )
    return row


def get_interview_by_token(token: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM interviews WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_dict(row)


def get_interview_by_id(interview_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM interviews WHERE id = ?", (interview_id,)
        ).fetchone()
    return _row_to_dict(row)


def update_interview_status(interview_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE interviews SET status = ? WHERE id = ?",
            (status, interview_id),
        )


def update_interview_scoring(
    interview_id: str,
    recommendation: str,
    overall_summary: str,
    strengths: list,
    areas_for_improvement: list,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE interviews
               SET recommendation = ?, overall_summary = ?,
                   strengths = ?, areas_for_improvement = ?, status = 'scored'
               WHERE id = ?""",
            (
                recommendation,
                overall_summary,
                json.dumps(strengths),
                json.dumps(areas_for_improvement),
                interview_id,
            ),
        )


# ── Questions ─────────────────────────────────────────────────────────────────

def save_question(
    interview_id: str,
    order_index: int,
    q_type: str,
    category: str,
    text: str,
    expected_answer_points: list,
) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "interview_id": interview_id,
        "order_index": order_index,
        "type": q_type,
        "category": category,
        "text": text,
        "expected_answer_points": json.dumps(expected_answer_points),
    }
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO questions
               (id, interview_id, order_index, type, category, text,
                expected_answer_points)
               VALUES (:id, :interview_id, :order_index, :type, :category,
                       :text, :expected_answer_points)""",
            row,
        )
    row["expected_answer_points"] = expected_answer_points
    return row


def get_question(interview_id: str, order_index: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE interview_id = ? AND order_index = ?",
            (interview_id, order_index),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["expected_answer_points"] = json.loads(d["expected_answer_points"])
    return d


def get_questions_for_interview(interview_id: str) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE interview_id = ? ORDER BY order_index",
            (interview_id,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["expected_answer_points"] = json.loads(d["expected_answer_points"])
        result.append(d)
    return result


# ── Answers ───────────────────────────────────────────────────────────────────

def save_answer(
    interview_id: str,
    question_id: str,
    order_index: int,
    answer_text: str,
) -> dict:
    row = {
        "id": str(uuid.uuid4()),
        "interview_id": interview_id,
        "question_id": question_id,
        "order_index": order_index,
        "answer_text": answer_text,
    }
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO answers
               (id, interview_id, question_id, order_index, answer_text)
               VALUES (:id, :interview_id, :question_id, :order_index, :answer_text)""",
            row,
        )
    return row


def update_answer_score(
    answer_id: str,
    score: float,
    feedback: str,
    communication_clarity: float,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE answers
               SET score = ?, feedback = ?, communication_clarity = ?
               WHERE id = ?""",
            (score, feedback, communication_clarity, answer_id),
        )


def get_answers_for_interview(interview_id: str) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM answers WHERE interview_id = ? ORDER BY order_index",
            (interview_id,),
        ).fetchall()
    return [dict(row) for row in rows]
