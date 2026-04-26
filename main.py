import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("interviewassist")

load_dotenv()
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import database as db
import llm_service as llm

ROLES = [
    "Data Engineer",
    "Data Scientist",
    "Power BI Developer",
    "Gen AI Engineer",
    "Business Analyst",
    "SAS Developer",
    "Other",
]


OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to your .env file.")
    log.info("API key loaded (len=%d)", len(OPENROUTER_API_KEY))
    log.info("LLM model: %s", llm.LLM_MODEL)
    db.init_db()
    log.info("Database initialised.")
    yield


app = FastAPI(title="InterviewAssist", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _avg(values: list) -> float:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _render(request: Request, name: str, context: dict = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context or {},
        status_code=status_code,
    )


# ── Interviewer routes ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def setup_page(request: Request, error: str = ""):
    return _render(request, "setup.html", {"roles": ROLES, "error": error})


@app.post("/setup")
async def create_interview(
    request: Request,
    candidate_name: str = Form(...),
    role: str = Form(...),
    custom_role_desc: str = Form(""),
    experience_years: int = Form(...),
    resume_text: str = Form(...),
):
    errors = []
    if not candidate_name.strip():
        errors.append("Candidate name is required.")
    if role not in ROLES:
        errors.append("Please select a valid role.")
    if role == "Other" and len(custom_role_desc.strip()) < 30:
        errors.append("Please describe the role (at least 30 characters).")
    if len(resume_text.strip()) < 50:
        errors.append("Resume / background must be at least 50 characters.")

    if errors:
        return _render(request, "setup.html", {
            "roles": ROLES,
            "error": " ".join(errors),
            "form": {
                "candidate_name": candidate_name,
                "role": role,
                "experience_years": experience_years,
                "resume_text": resume_text,
            },
        })

    role_desc = custom_role_desc.strip() if role == "Other" else llm.ROLE_DESCRIPTIONS[role]

    interview = db.create_interview(
        candidate_name=candidate_name.strip(),
        role=role,
        role_desc=role_desc,
        experience_years=experience_years,
        resume_text=resume_text.strip(),
        api_key=OPENROUTER_API_KEY,
    )

    return RedirectResponse(f"/i/{interview['id']}", status_code=303)


@app.get("/i/{interview_id}", response_class=HTMLResponse)
async def interview_created_page(request: Request, interview_id: str):
    interview = db.get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    candidate_link = f"{_base_url(request)}/c/{interview['token']}"
    return _render(request, "created.html", {
        "interview": interview,
        "candidate_link": candidate_link,
    })


@app.get("/i/{interview_id}/results", response_class=HTMLResponse)
async def results_page(request: Request, interview_id: str):
    interview = db.get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    if interview["status"] != "scored":
        return RedirectResponse(f"/i/{interview_id}")

    questions = db.get_questions_for_interview(interview_id)
    answers = db.get_answers_for_interview(interview_id)
    answer_by_qid = {a["question_id"]: a for a in answers}

    all_scores  = [a["score"] for a in answers if a.get("score") is not None]
    tech_scores = [answers[i]["score"] for i in range(min(4, len(answers))) if answers[i].get("score") is not None]
    proj_scores = [answers[i]["score"] for i in range(4, min(6, len(answers))) if answers[i].get("score") is not None]
    beh_scores  = [answers[i]["score"] for i in range(6, min(8, len(answers))) if answers[i].get("score") is not None]

    strengths    = json.loads(interview.get("strengths") or "[]")
    improvements = json.loads(interview.get("areas_for_improvement") or "[]")

    return _render(request, "results.html", {
        "interview": interview,
        "questions": questions,
        "answer_by_qid": answer_by_qid,
        "overall_score": _avg(all_scores),
        "technical_score": _avg(tech_scores),
        "project_score": _avg(proj_scores),
        "behavioural_score": _avg(beh_scores),
        "strengths": strengths,
        "improvements": improvements,
        "experience_label": llm.get_experience_label(interview["experience_years"]),
    })


# ── Candidate routes ──────────────────────────────────────────────────────────

@app.get("/c/{token}", response_class=HTMLResponse)
async def welcome_page(request: Request, token: str):
    interview = db.get_interview_by_token(token)
    if not interview:
        return _render(request, "error.html",
                       {"message": "Invalid interview link. Please check the URL."},
                       status_code=404)

    if interview["status"] in ("completed", "scored"):
        return _render(request, "error.html",
                       {"message": "This interview has already been completed. Thank you."})

    if interview["status"] == "in_progress":
        answers = db.get_answers_for_interview(interview["id"])
        next_q = len(answers) + 1
        if next_q <= 9:
            return RedirectResponse(f"/c/{token}/q/{next_q}")

    return _render(request, "welcome.html", {"interview": interview})


@app.post("/c/{token}/start")
async def start_interview(request: Request, token: str):
    interview = db.get_interview_by_token(token)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")

    log.info("Starting interview id=%s for candidate=%s", interview["id"], interview["candidate_name"])
    db.update_interview_status(interview["id"], "in_progress")

    try:
        experience_label = llm.get_experience_label(interview["experience_years"])
        questions = llm.generate_all_questions(
            api_key=interview["api_key"],
            role=interview["role"],
            role_desc=interview["role_desc"],
            experience_years=interview["experience_years"],
            experience_label=experience_label,
            resume_text=interview["resume_text"],
        )
        for q in questions:
            db.save_question(
                interview_id=interview["id"],
                order_index=q["order_index"],
                q_type=q["type"],
                category=q["category"],
                text=q["text"],
                expected_answer_points=q.get("expected_answer_points", []),
            )
        log.info("Saved all 9 questions for interview id=%s", interview["id"])
    except Exception as e:
        log.error("Failed to generate questions for interview id=%s: %s", interview["id"], e, exc_info=True)
        db.update_interview_status(interview["id"], "ready")
        return RedirectResponse(f"/c/{token}?error={str(e)[:80]}", status_code=303)

    return RedirectResponse(f"/c/{token}/q/1", status_code=303)


@app.get("/c/{token}/q/{n}", response_class=HTMLResponse)
async def question_page(request: Request, token: str, n: int, error: str = ""):
    interview = db.get_interview_by_token(token)
    if not interview or n < 1 or n > 9:
        raise HTTPException(status_code=404)

    question = db.get_question(interview["id"], order_index=n - 1)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    answers = db.get_answers_for_interview(interview["id"])
    answered_indices = {a["order_index"] for a in answers}
    existing_answer = next((a for a in answers if a["order_index"] == n - 1), None)

    return _render(request, "interview.html", {
        "interview": interview,
        "question": question,
        "question_number": n,
        "total_questions": 9,
        "progress_pct": int((n - 1) / 9 * 100),
        "answered_indices": answered_indices,
        "existing_answer": existing_answer,
        "error": error,
    })


@app.post("/c/{token}/q/{n}")
async def submit_answer(
    request: Request,
    token: str,
    n: int,
    answer_text: str = Form(""),
    audio_file: Optional[UploadFile] = File(None),
):
    interview = db.get_interview_by_token(token)
    if not interview or n < 1 or n > 9:
        raise HTTPException(status_code=404)

    # ── Determine answer text and optional audio path ──────────────────────
    audio_path: Optional[str] = None
    is_audio = audio_file and audio_file.size and audio_file.size > 0

    if is_audio:
        audio_dir = Path("audio") / interview["id"]
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = str(audio_dir / f"q{n}.webm")
        content = await audio_file.read()
        Path(audio_path).write_bytes(content)
        saved_text = "[transcription pending]"
        log.info("Audio saved: %s (%d bytes)", audio_path, len(content))
    else:
        saved_text = answer_text.strip()
        if len(saved_text) < 20:
            return RedirectResponse(
                f"/c/{token}/q/{n}?error=Please+provide+a+more+detailed+answer+(at+least+20+characters).",
                status_code=303,
            )

    question = db.get_question(interview["id"], order_index=n - 1)
    if not question:
        raise HTTPException(status_code=404)

    db.save_answer(
        interview_id=interview["id"],
        question_id=question["id"],
        order_index=n - 1,
        answer_text=saved_text,
        audio_file_path=audio_path,
    )

    if n < 9:
        return RedirectResponse(f"/c/{token}/q/{n+1}", status_code=303)
    else:
        db.update_interview_status(interview["id"], "completed")
        try:
            _run_scoring(interview)
        except Exception:
            pass
        return RedirectResponse(f"/c/{token}/done", status_code=303)


@app.post("/c/{token}/finish")
async def finish_interview(request: Request, token: str):
    interview = db.get_interview_by_token(token)
    if not interview:
        raise HTTPException(status_code=404)
    db.update_interview_status(interview["id"], "completed")
    try:
        _run_scoring(interview)
    except Exception as e:
        log.error("Scoring failed on manual finish for interview id=%s: %s", interview["id"], e, exc_info=True)
    return RedirectResponse(f"/c/{token}/done", status_code=303)


@app.get("/c/{token}/done", response_class=HTMLResponse)
async def done_page(request: Request, token: str):
    interview = db.get_interview_by_token(token)
    if not interview:
        raise HTTPException(status_code=404)
    return _render(request, "thankyou.html", {"interview": interview})


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/i/{interview_id}/export")
async def export_results(interview_id: str):
    interview = db.get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404)

    questions = db.get_questions_for_interview(interview_id)
    answers   = db.get_answers_for_interview(interview_id)
    answer_by_qid = {a["question_id"]: a for a in answers}
    all_scores = [a["score"] for a in answers if a.get("score") is not None]

    lines = [
        "InterviewAssist — Results Report",
        "=" * 50,
        f"Candidate:  {interview['candidate_name']}",
        f"Role:       {interview['role']}",
        f"Experience: {interview['experience_years']} years",
        f"Overall:    {_avg(all_scores)}/5.0",
        f"Decision:   {(interview.get('recommendation') or 'pending').upper()}",
        "",
        interview.get("overall_summary", ""),
        "",
        "=" * 50,
    ]
    for q in questions:
        ans = answer_by_qid.get(q["id"], {})
        lines += [
            f"\nQ{q['order_index']+1} [{q['type'].upper()}] {q['category']}",
            f"Question: {q['text']}",
            f"Score: {ans.get('score', '—')}/5  |  Clarity: {ans.get('communication_clarity', '—')}/5",
            f"Feedback: {ans.get('feedback', '')}",
            f"Answer:\n{ans.get('answer_text', '')}",
            "-" * 40,
        ]

    filename = f"interview_{interview['candidate_name'].replace(' ', '_')}.txt"
    return PlainTextResponse(
        content="\n".join(lines),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Status API ────────────────────────────────────────────────────────────────

@app.get("/api/i/{interview_id}/status")
async def get_status(interview_id: str):
    interview = db.get_interview_by_id(interview_id)
    if not interview:
        raise HTTPException(status_code=404)
    return {"status": interview["status"]}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _run_scoring(interview: dict) -> None:
    questions      = db.get_questions_for_interview(interview["id"])
    answers        = db.get_answers_for_interview(interview["id"])
    answer_by_idx  = {a["order_index"]: a for a in answers}

    qa_pairs = [
        {
            "order_index": q["order_index"],
            "type": q["type"],
            "category": q["category"],
            "text": q["text"],
            "expected_answer_points": q["expected_answer_points"],
            "answer_text": answer_by_idx.get(q["order_index"], {}).get("answer_text", ""),
        }
        for q in questions
    ]

    result = llm.score_all_answers(
        api_key=interview["api_key"],
        interview_context={
            "candidate_name": interview["candidate_name"],
            "role": interview["role"],
            "role_desc": interview["role_desc"],
            "experience_label": llm.get_experience_label(interview["experience_years"]),
        },
        questions_and_answers=qa_pairs,
    )

    for entry in result.get("scores", []):
        ans = answer_by_idx.get(entry["order_index"])
        if ans:
            db.update_answer_score(
                answer_id=ans["id"],
                score=entry.get("score", 0),
                feedback=entry.get("feedback", ""),
                communication_clarity=entry.get("communication_clarity", 0),
            )

    db.update_interview_scoring(
        interview_id=interview["id"],
        recommendation=result.get("recommendation", "hold"),
        overall_summary=result.get("overall_summary", ""),
        strengths=result.get("strengths", []),
        areas_for_improvement=result.get("areas_for_improvement", []),
    )
