import streamlit as st
import openai

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

QUESTION_TYPE_COLOURS = {
    "technical":  "#2563EB",
    "project":    "#7C3AED",
    "behavioral": "#059669",
    "coding":     "#D97706",
}

RECOMMENDATION_CONFIG = {
    "strong_hire": ("success", "✓  STRONG HIRE"),
    "hire":        ("success", "✓  HIRE"),
    "hold":        ("warning", "⚠  HOLD — FURTHER REVIEW"),
    "no_hire":     ("error",   "✗  NO HIRE"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _type_badge(q_type: str) -> str:
    colour = QUESTION_TYPE_COLOURS.get(q_type, "#6B7280")
    label = q_type.upper()
    return (
        f'<span style="background:{colour};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def _avg(values: list) -> float:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _score_colour(score) -> str:
    if score is None:
        return "#9CA3AF"
    if score >= 4:
        return "#16A34A"
    if score >= 3:
        return "#65A30D"
    if score >= 2:
        return "#D97706"
    return "#DC2626"


# ── Interviewer view ──────────────────────────────────────────────────────────

def run_interviewer_view():
    st.set_page_config(page_title="InterviewAssist — Interviewer", layout="centered")

    if "iv_screen" not in st.session_state:
        st.session_state.iv_screen = "setup"

    screen = st.session_state.iv_screen

    if screen == "setup":
        _render_setup_screen()
    elif screen == "created":
        _render_created_screen()
    elif screen == "results":
        _render_results_screen()


def _render_setup_screen():
    st.title("InterviewAssist")
    st.caption("Set up a new interview session and share the link with your candidate.")
    st.divider()

    with st.form("setup_form"):
        candidate_name = st.text_input("Candidate Name", placeholder="e.g. Jane Smith")

        role = st.selectbox("Role", ROLES)

        custom_role_desc = ""
        if role == "Other":
            custom_role_desc = st.text_area(
                "Describe the role",
                placeholder="Describe the role, key skills and responsibilities (min 30 characters)...",
                height=100,
            )

        experience_years = st.slider("Years of Experience", min_value=0, max_value=20, value=3)

        resume_text = st.text_area(
            "Resume / Background",
            placeholder="Paste the candidate's CV or a brief summary of their background here...",
            height=220,
        )

        api_key = st.text_input(
            "OpenRouter API Key",
            type="password",
            placeholder="sk-or-...",
            help="Get your free key at openrouter.ai",
        )

        submitted = st.form_submit_button("Create Interview →", use_container_width=True)

    if submitted:
        errors = []
        if not candidate_name.strip():
            errors.append("Candidate name is required.")
        if role == "Other" and len(custom_role_desc.strip()) < 30:
            errors.append("Please describe the role (at least 30 characters).")
        if len(resume_text.strip()) < 50:
            errors.append("Resume / background must be at least 50 characters.")
        if not api_key.strip():
            errors.append("OpenRouter API key is required.")

        if errors:
            for e in errors:
                st.error(e)
            return

        role_desc = custom_role_desc.strip() if role == "Other" else llm.ROLE_DESCRIPTIONS[role]

        interview = db.create_interview(
            candidate_name=candidate_name.strip(),
            role=role,
            role_desc=role_desc,
            experience_years=experience_years,
            resume_text=resume_text.strip(),
        )

        st.session_state.iv_api_key = api_key.strip()
        st.session_state.iv_interview_id = interview["id"]

        base_url = st.get_option("browser.serverAddress") or "localhost"
        port = st.get_option("browser.serverPort") or 8501
        st.session_state.iv_candidate_link = f"http://{base_url}:{port}/?token={interview['token']}"

        st.session_state.iv_screen = "created"
        st.rerun()


def _render_created_screen():
    interview_id = st.session_state.get("iv_interview_id")
    candidate_link = st.session_state.get("iv_candidate_link")

    interview = db.get_interview_by_id(interview_id) if interview_id else None
    if not interview:
        st.error("Interview session not found. Please create a new one.")
        if st.button("Start Over"):
            st.session_state.iv_screen = "setup"
            st.rerun()
        return

    st.title("Interview Created")
    st.success(f"Session ready for **{interview['candidate_name']}** — {interview['role']}")
    st.divider()

    st.subheader("Candidate Link")
    st.caption("Share this link with your candidate. They complete the interview on their own device.")
    st.code(candidate_link, language=None)

    st.divider()
    st.subheader("Interview Status")

    status = interview["status"]
    status_map = {
        "ready":       ("🟡", "Waiting — candidate has not started yet"),
        "in_progress": ("🔵", "In progress — candidate is answering questions"),
        "completed":   ("🟠", "Completed — scoring in progress..."),
        "scored":      ("🟢", "Scored — results are ready"),
    }
    icon, label = status_map.get(status, ("⚪", status))
    st.markdown(f"**{icon} {label}**")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    with col2:
        results_ready = status == "scored"
        if st.button("📊 View Results", use_container_width=True, disabled=not results_ready):
            st.session_state.iv_screen = "results"
            st.rerun()

    if not results_ready:
        st.caption("Results will be available once the candidate finishes and scoring completes.")


def _render_results_screen():
    interview_id = st.session_state.get("iv_interview_id")
    interview = db.get_interview_by_id(interview_id) if interview_id else None

    if not interview:
        st.error("Interview not found.")
        return

    questions = db.get_questions_for_interview(interview_id)
    answers = db.get_answers_for_interview(interview_id)

    answer_by_qid = {a["question_id"]: a for a in answers}

    st.title("Interview Results")
    st.divider()

    # Summary card
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Candidate**  \n{interview['candidate_name']}")
        c2.markdown(f"**Role**  \n{interview['role']}")
        c3.markdown(f"**Experience**  \n{interview['experience_years']} years")

    # Recommendation badge
    scores_list = [a.get("score") for a in answers if a.get("score") is not None]

    if answers and all(a.get("score") is not None for a in answers):
        first_answer = answers[0] if answers else {}
    else:
        first_answer = {}

    # Load recommendation from scoring (stored as part of first answer feedback pattern)
    # We stored it in session state during scoring
    recommendation = st.session_state.get("iv_recommendation")

    if recommendation and recommendation in RECOMMENDATION_CONFIG:
        kind, label = RECOMMENDATION_CONFIG[recommendation]
        getattr(st, kind)(f"**{label}**")
    elif scores_list:
        avg = _avg(scores_list)
        min_score = min(scores_list)
        zero_count = scores_list.count(0)
        if avg >= 4.0 and min_score >= 2:
            rec = "strong_hire"
        elif avg >= 3.0 and min_score >= 1:
            rec = "hire"
        elif avg >= 2.0:
            rec = "hold"
        else:
            rec = "no_hire"
        kind, label = RECOMMENDATION_CONFIG[rec]
        getattr(st, kind)(f"**{label}**")

    st.divider()

    # Score metrics
    tech_scores = [answers[i].get("score") for i in range(min(4, len(answers)))]
    proj_scores = [answers[i].get("score") for i in range(4, min(6, len(answers)))]
    beh_scores  = [answers[i].get("score") for i in range(6, min(8, len(answers)))]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Overall Score",    f"{_avg(scores_list)} / 5.0")
    m2.metric("Technical",        f"{_avg(tech_scores)} / 5.0")
    m3.metric("Project",          f"{_avg(proj_scores)} / 5.0")
    m4.metric("Behavioural",      f"{_avg(beh_scores)} / 5.0")

    st.divider()

    # Overall summary and strengths
    overall_summary = st.session_state.get("iv_overall_summary", "")
    strengths = st.session_state.get("iv_strengths", [])
    improvements = st.session_state.get("iv_improvements", [])

    if overall_summary:
        st.subheader("Summary")
        st.write(overall_summary)

        col_s, col_i = st.columns(2)
        with col_s:
            st.subheader("Strengths")
            for s in strengths:
                st.markdown(f"- {s}")
        with col_i:
            st.subheader("Areas for Improvement")
            for a in improvements:
                st.markdown(f"- {a}")

        st.divider()

    # Per-question breakdown
    st.subheader("Question-by-Question Breakdown")

    for q in questions:
        ans = answer_by_qid.get(q["id"], {})
        score = ans.get("score")
        clarity = ans.get("communication_clarity")
        feedback = ans.get("feedback", "")
        answer_text = ans.get("answer_text", "(no answer recorded)")

        colour = _score_colour(score)
        score_display = f"{score}/5" if score is not None else "—"

        with st.expander(
            f"Q{q['order_index']+1}  ·  {q['category']}  ·  Score: {score_display}"
        ):
            st.markdown(_type_badge(q["type"]), unsafe_allow_html=True)
            st.markdown(f"**Question:** {q['text']}")
            st.markdown("---")

            col_sc, col_cl = st.columns(2)
            with col_sc:
                st.markdown(
                    f"**Score:** <span style='color:{colour};font-weight:700;font-size:1.1rem'>"
                    f"{score_display}</span>",
                    unsafe_allow_html=True,
                )
                if score is not None:
                    st.progress(score / 5)
            with col_cl:
                if clarity is not None:
                    st.markdown(f"**Communication Clarity:** {clarity:.1f} / 5.0")

            if feedback:
                st.markdown(f"**Feedback:** {feedback}")

            st.markdown("**Candidate's Answer:**")
            st.text_area("", value=answer_text, disabled=True, key=f"ans_{q['id']}", height=100)

    # Export
    st.divider()
    export_lines = [
        f"InterviewAssist — Results Report",
        f"Candidate: {interview['candidate_name']}",
        f"Role: {interview['role']} | Experience: {interview['experience_years']} years",
        f"Overall Score: {_avg(scores_list)}/5.0",
        "",
    ]
    for q in questions:
        ans = answer_by_qid.get(q["id"], {})
        export_lines += [
            f"Q{q['order_index']+1} [{q['type'].upper()}] {q['category']}",
            f"Question: {q['text']}",
            f"Score: {ans.get('score', '—')}/5  |  Clarity: {ans.get('communication_clarity', '—')}/5",
            f"Feedback: {ans.get('feedback', '')}",
            f"Answer: {ans.get('answer_text', '')}",
            "",
        ]

    st.download_button(
        "⬇ Download Results (.txt)",
        data="\n".join(export_lines),
        file_name=f"interview_{interview['candidate_name'].replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
    )


# ── Candidate view ────────────────────────────────────────────────────────────

def run_candidate_view(token: str):
    st.set_page_config(page_title="InterviewAssist — Interview", layout="centered")

    interview = db.get_interview_by_token(token)
    if not interview:
        st.error("Invalid interview link. Please check the URL and try again.")
        st.stop()

    if interview["status"] in ("completed", "scored"):
        st.info("This interview has already been completed. Thank you.")
        st.stop()

    # Initialise candidate session state
    if "cd_screen" not in st.session_state:
        st.session_state.cd_screen = "welcome"
        st.session_state.cd_interview = interview
        st.session_state.cd_questions = []
        st.session_state.cd_current_q_index = 0
        st.session_state.cd_answers = []
        st.session_state.cd_error = None
        st.session_state.cd_api_key = None

    # Resume-after-crash: restore progress from DB
    if interview["status"] == "in_progress" and st.session_state.cd_screen == "welcome":
        saved_questions = db.get_questions_for_interview(interview["id"])
        saved_answers = db.get_answers_for_interview(interview["id"])
        if saved_questions:
            st.session_state.cd_questions = saved_questions
            st.session_state.cd_answers = [a["answer_text"] for a in saved_answers]
            st.session_state.cd_current_q_index = len(saved_answers)
            st.session_state.cd_screen = "interview"

    screen = st.session_state.cd_screen

    if screen == "welcome":
        _render_welcome_screen(interview)
    elif screen == "interview":
        _render_interview_screen(interview)
    elif screen == "thankyou":
        _render_thankyou_screen(interview)


def _render_welcome_screen(interview: dict):
    st.title("Welcome to Your Interview")
    st.markdown(
        f"Hello **{interview['candidate_name']}**, you have been invited to complete "
        f"a technical interview for the **{interview['role']}** position."
    )
    st.divider()

    st.subheader("Before You Begin")
    st.markdown("""
- Find a quiet, well-lit location
- Ensure you have **30–40 minutes** of uninterrupted time
- Read each question carefully before answering
- There are **9 questions** covering technical knowledge, your experience, and problem-solving
- Type your answers — take your time, quality matters more than speed
- The interview is AI-assessed. Answer honestly and independently
""")

    st.divider()

    api_key = st.text_input(
        "OpenRouter API Key",
        type="password",
        placeholder="sk-or-...",
        help="Required to generate your questions. Ask your interviewer if you don't have one.",
    )

    if st.button("Begin Interview →", use_container_width=True):
        if not api_key.strip():
            st.error("Please enter the OpenRouter API key provided by your interviewer.")
            return
        db.update_interview_status(interview["id"], "in_progress")
        st.session_state.cd_api_key = api_key.strip()
        st.session_state.cd_screen = "interview"
        st.rerun()


def _render_interview_screen(interview: dict):
    current_idx = st.session_state.cd_current_q_index
    questions = st.session_state.cd_questions
    api_key = st.session_state.get("cd_api_key", "")

    # Generate the next question if needed
    if len(questions) == current_idx:
        _, q_type, q_focus = llm.QUESTION_PLAN[current_idx]
        with st.spinner("Preparing your next question..."):
            try:
                prev_q_texts = [q["text"] for q in questions]
                experience_label = llm.get_experience_label(interview["experience_years"])
                q_dict = llm.generate_question(
                    api_key=api_key,
                    role=interview["role"],
                    role_desc=interview["role_desc"],
                    experience_years=interview["experience_years"],
                    experience_label=experience_label,
                    resume_text=interview["resume_text"],
                    question_number=current_idx + 1,
                    question_type=q_type,
                    question_focus=q_focus,
                    previous_questions=prev_q_texts,
                )
                saved_q = db.save_question(
                    interview_id=interview["id"],
                    order_index=current_idx,
                    q_type=q_dict["type"],
                    category=q_dict["category"],
                    text=q_dict["text"],
                    expected_answer_points=q_dict.get("expected_answer_points", []),
                )
                st.session_state.cd_questions.append(saved_q)
                questions = st.session_state.cd_questions
            except openai.AuthenticationError:
                st.error("Invalid API key. Please ask your interviewer for the correct key.")
                st.stop()
            except openai.RateLimitError:
                st.error("Rate limit reached. Please wait 30 seconds and refresh the page.")
                st.stop()
            except Exception as e:
                st.error(f"Could not generate question: {e}. Please refresh to try again.")
                st.stop()

    current_question = questions[current_idx]

    # Progress bar
    progress_val = current_idx / 9
    st.progress(progress_val)
    st.caption(f"Question {current_idx + 1} of 9")

    # Question type badge
    st.markdown(
        _type_badge(current_question["type"]) + f"&nbsp; **{current_question['category']}**",
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Question text
    st.markdown(f"### {current_question['text']}")

    if current_question["type"] == "coding":
        st.info(
            "💡 Describe your approach, write pseudocode, or write actual code — "
            "whatever feels most natural to you."
        )

    st.markdown("")

    # Answer input
    answer_key = f"answer_input_{current_idx}"
    answer_text = st.text_area(
        "Your Answer",
        key=answer_key,
        height=180,
        placeholder="Type your answer here...",
    )

    # Error from previous attempt
    if st.session_state.get("cd_error"):
        st.warning(st.session_state.cd_error)
        st.session_state.cd_error = None

    submit_label = "Submit & Next →" if current_idx < 8 else "Submit & Finish ✓"

    if st.button(submit_label, use_container_width=True):
        if len(answer_text.strip()) < 20:
            st.session_state.cd_error = "Please provide a more detailed answer (at least 20 characters)."
            st.rerun()
            return

        # Save answer to DB
        db.save_answer(
            interview_id=interview["id"],
            question_id=current_question["id"],
            order_index=current_idx,
            answer_text=answer_text.strip(),
        )
        st.session_state.cd_answers.append(answer_text.strip())

        if current_idx < 8:
            st.session_state.cd_current_q_index += 1
            st.rerun()
        else:
            # Final question submitted — score everything
            db.update_interview_status(interview["id"], "completed")
            with st.spinner("Submitting your interview and generating results..."):
                _run_scoring(interview, api_key)
            st.session_state.cd_screen = "thankyou"
            st.rerun()


def _render_thankyou_screen(interview: dict):
    st.title("Interview Complete")
    st.success(
        f"Thank you, **{interview['candidate_name']}**. "
        "Your responses have been submitted successfully."
    )
    st.markdown(
        "The interviewer will review your results shortly. "
        "You may now close this window."
    )
    st.balloons()


# ── Scoring ───────────────────────────────────────────────────────────────────

def _run_scoring(interview: dict, api_key: str) -> None:
    questions = db.get_questions_for_interview(interview["id"])
    answers = db.get_answers_for_interview(interview["id"])

    answer_by_idx = {a["order_index"]: a for a in answers}

    qa_pairs = []
    for q in questions:
        ans = answer_by_idx.get(q["order_index"], {})
        qa_pairs.append({
            "order_index": q["order_index"],
            "type": q["type"],
            "category": q["category"],
            "text": q["text"],
            "expected_answer_points": q["expected_answer_points"],
            "answer_text": ans.get("answer_text", ""),
        })

    experience_label = llm.get_experience_label(interview["experience_years"])

    try:
        result = llm.score_all_answers(
            api_key=api_key,
            interview_context={
                "candidate_name": interview["candidate_name"],
                "role": interview["role"],
                "role_desc": interview["role_desc"],
                "experience_label": experience_label,
            },
            questions_and_answers=qa_pairs,
        )
    except Exception as e:
        st.error(f"Scoring failed: {e}. The interviewer can retry from the dashboard.")
        return

    # Write scores back to DB
    for score_entry in result.get("scores", []):
        idx = score_entry["order_index"]
        ans = answer_by_idx.get(idx)
        if ans:
            db.update_answer_score(
                answer_id=ans["id"],
                score=score_entry.get("score", 0),
                feedback=score_entry.get("feedback", ""),
                communication_clarity=score_entry.get("communication_clarity", 0),
            )

    # Store summary fields in session state for results screen
    st.session_state.iv_recommendation = result.get("recommendation")
    st.session_state.iv_overall_summary = result.get("overall_summary", "")
    st.session_state.iv_strengths = result.get("strengths", [])
    st.session_state.iv_improvements = result.get("areas_for_improvement", [])

    db.update_interview_status(interview["id"], "scored")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    db.init_db()
    token = st.query_params.get("token", None)
    if token:
        run_candidate_view(token)
    else:
        run_interviewer_view()


if __name__ == "__main__":
    main()
