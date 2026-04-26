import json
import logging
import re
from openai import OpenAI, APIError

log = logging.getLogger("interviewassist.llm")

# Tried in order on 429/404; all verified against OpenRouter /models endpoint
LLM_MODELS = [
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-3-27b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m2.5:free",
]
LLM_MODEL = LLM_MODELS[0]  # used for logging

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

QUESTION_PLAN = [
    (0, "technical",  "core concepts and fundamentals for the role"),
    (1, "technical",  "specific tools and technologies commonly used"),
    (2, "technical",  "scenario-based problem solving"),
    (3, "technical",  "advanced concept appropriate to experience level"),
    (4, "project",    "a specific project from the resume — what was built and how"),
    (5, "project",    "challenges faced and outcomes achieved in a project"),
    (6, "behavioral", "handling a conflict or disagreement at work"),
    (7, "behavioral", "teamwork, collaboration, or leadership"),
    (8, "coding",     "text-based coding or analytical problem — describe approach and solution"),
]

ROLE_DESCRIPTIONS = {
    "Data Engineer": (
        "A Data Engineer designs, builds, and maintains scalable data pipelines and infrastructure. "
        "Core competencies include ETL/ELT pipeline development, SQL and Python, Apache Spark, "
        "cloud data platforms (AWS Glue, Azure Data Factory, GCP Dataflow), orchestration tools "
        "such as Apache Airflow and dbt, data warehousing with Snowflake, Redshift, or BigQuery, "
        "dimensional data modelling, and ensuring data quality and reliability at scale."
    ),
    "Data Scientist": (
        "A Data Scientist applies statistical modelling and machine learning to extract insights "
        "and build predictive systems. Core competencies include Python (pandas, scikit-learn, "
        "PyTorch, TensorFlow), statistical analysis, feature engineering, model evaluation and "
        "validation, A/B testing, experiment design, data visualisation, and translating "
        "business problems into analytical solutions."
    ),
    "Power BI Developer": (
        "A Power BI Developer builds enterprise analytics solutions on the Microsoft BI stack. "
        "Core competencies include Power BI Desktop and Service, DAX formula authoring, "
        "Power Query and M language for data transformation, dimensional data modelling "
        "(star schema, relationships), report and dashboard design, performance optimisation, "
        "and connecting to diverse data sources including SQL Server, SharePoint, and REST APIs."
    ),
    "Gen AI Engineer": (
        "A Gen AI Engineer designs and productionises systems leveraging large language models "
        "and generative AI. Core competencies include prompt engineering, retrieval-augmented "
        "generation (RAG), LangChain and LlamaIndex frameworks, vector databases (Pinecone, "
        "Chroma, Weaviate), fine-tuning and PEFT methods, LLM evaluation and safety, "
        "and deploying AI-powered applications at scale."
    ),
    "Business Analyst": (
        "A Business Analyst bridges business requirements and technical delivery. Core competencies "
        "include requirements elicitation and documentation, process mapping and gap analysis, "
        "SQL for data extraction, data visualisation tools, stakeholder management, writing "
        "user stories and acceptance criteria, facilitating workshops, conducting UAT, and "
        "translating analytical findings into actionable business recommendations."
    ),
    "SAS Developer": (
        "A SAS Developer builds analytical solutions using the SAS platform. Core competencies "
        "include Base SAS programming (DATA step, PROC SQL, macros), SAS/STAT and SAS Enterprise "
        "Guide, ETL development in SAS DI Studio, clinical or financial data processing, "
        "performance tuning of SAS programs, SAS Viya and Visual Analytics, and integration "
        "with external databases via LIBNAME engines."
    ),
    "Other": "",
}

EXPERIENCE_BANDS = [
    (range(0, 2),  "entry-level (0-1 years)",   "Focus on fundamentals and basic implementations. Avoid system design or architecture questions."),
    (range(2, 5),  "mid-level (2-4 years)",      "Expect familiarity with trade-offs, optimisation, and design decisions. Intermediate depth."),
    (range(5, 8),  "senior (5-7 years)",         "Expect system design thinking, architectural trade-offs, and complex problem solving."),
    (range(8, 51), "lead/principal (8+ years)",  "Expect leadership context, large-scale system design, and mentoring or strategy scenarios."),
]


def get_client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://interviewassist.local",
            "X-Title": "InterviewAssist",
        },
    )


def get_experience_label(experience_years: int) -> str:
    for band, label, _ in EXPERIENCE_BANDS:
        if experience_years in band:
            return label
    return "lead/principal (8+ years)"


def _get_difficulty_note(experience_years: int) -> str:
    for band, _, note in EXPERIENCE_BANDS:
        if experience_years in band:
            return note
    return EXPERIENCE_BANDS[-1][2]


def _extract_json_object(text: str) -> dict:
    text = re.sub(r"```(?:json)?\n?", "", text).strip().replace("```", "")
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object in response: {text[:300]}")
    return json.loads(text[start:end])


def _extract_json_array(text: str) -> list:
    text = re.sub(r"```(?:json)?\n?", "", text).strip().replace("```", "")
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array in response: {text[:300]}")
    return json.loads(text[start:end])


def generate_all_questions(
    api_key: str,
    role: str,
    role_desc: str,
    experience_years: int,
    experience_label: str,
    resume_text: str,
) -> list:
    difficulty_note = _get_difficulty_note(experience_years)
    resume_snippet = (resume_text or "")[:3000]

    plan_text = "\n".join(
        f"  {i+1}. type={q_type}, focus={q_focus}"
        for i, (_, q_type, q_focus) in enumerate(QUESTION_PLAN)
    )

    system_prompt = (
        "You are an expert technical interviewer. "
        "Always respond with a valid JSON array only — no markdown, no prose outside the JSON."
    )

    user_prompt = f"""Generate all 9 interview questions for the following candidate in one response.

Candidate profile:
- Role: {role}
- Role description: {role_desc}
- Experience level: {experience_label} ({experience_years} years)
- Difficulty calibration: {difficulty_note}
- Resume / background:
{resume_snippet}

Question plan (follow this order exactly):
{plan_text}

Rules:
- No two questions may cover the same topic or skill area.
- Tailor every question to the candidate's resume where relevant.
- Questions 1-4 are technical, 5-6 are project-based, 7-8 are behavioural, 9 is a coding/analytical problem.
- Q9 (coding) must be basic-to-intermediate difficulty only — a strong candidate should be able to describe their full approach in writing within 10 minutes. No system design or complex algorithm questions.

Return a JSON array of exactly 9 objects, one per question, in order:
[
  {{
    "order_index": 0,
    "type": "<type from plan>",
    "category": "<specific skill or area, e.g. 'SQL window functions'>",
    "text": "<the full question, 1-3 sentences, no numbering prefix>",
    "expected_answer_points": ["<key point 1>", "<key point 2>", "<key point 3>"]
  }},
  ...
]"""

    last_exc: Exception = None
    for model in LLM_MODELS:
        log.info("Batch question generation — trying model: %s", model)
        try:
            client = get_client(api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            questions = _extract_json_array(response.choices[0].message.content)
            if len(questions) != 9:
                raise ValueError(f"Expected 9 questions, got {len(questions)}")
            log.info("All 9 questions generated with model: %s", model)
            return questions
        except APIError as e:
            log.warning("Model %s unavailable (%s) — trying next", model, type(e).__name__)
            last_exc = e
            continue
        except (ValueError, json.JSONDecodeError) as e:
            log.warning("Model %s parse error: %s — trying next", model, str(e)[:120])
            last_exc = e
            continue
    raise last_exc


def generate_question(
    api_key: str,
    role: str,
    role_desc: str,
    experience_years: int,
    experience_label: str,
    resume_text: str,
    question_number: int,
    question_type: str,
    question_focus: str,
    previous_questions: list,
) -> dict:
    difficulty_note = _get_difficulty_note(experience_years)
    resume_snippet = (resume_text or "")[:3000]

    prev_text = (
        "\n".join(f"  {i+1}. {q}" for i, q in enumerate(previous_questions))
        if previous_questions else "  None yet."
    )

    system_prompt = (
        "You are an expert technical interviewer. "
        "Always respond with a valid JSON object only — no markdown, no prose outside the JSON."
    )

    user_prompt = f"""You are conducting question {question_number} of 9 for a {role} interview.

Candidate profile:
- Role: {role}
- Role description: {role_desc}
- Experience level: {experience_label} ({experience_years} years)
- Resume / background:
{resume_snippet}

Question specification:
- Number: {question_number} of 9
- Type: {question_type}
- Focus: {question_focus}
- Difficulty calibration: {difficulty_note}

Previously asked questions (DO NOT repeat these topics):
{prev_text}

Generate exactly one interview question. Return this JSON object only:
{{
  "type": "{question_type}",
  "category": "<specific skill or area, e.g. 'SQL window functions'>",
  "text": "<the full question, 1-3 sentences, no numbering prefix>",
  "expected_answer_points": [
    "<key point 1 a strong answer must cover>",
    "<key point 2>",
    "<key point 3>"
  ]
}}"""

    def _call(prompt: str, model: str) -> dict:
        client = get_client(api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return _extract_json_object(response.choices[0].message.content)

    last_exc: Exception = None
    for model in LLM_MODELS:
        log.info("Trying model: %s", model)
        try:
            result = _call(user_prompt, model)
            log.info("Success with model: %s", model)
            return result
        except APIError as e:
            log.warning("Model %s unavailable (%s) — trying next", model, type(e).__name__)
            last_exc = e
            continue
        except (ValueError, json.JSONDecodeError):
            simplified = (
                f"Generate one {question_type} interview question for a {role} "
                f"with {experience_years} years of experience. Focus: {question_focus}.\n"
                f'Return JSON only: {{"type": "{question_type}", "category": "...", '
                f'"text": "...", "expected_answer_points": ["...", "...", "..."]}}'
            )
            try:
                result = _call(simplified, model)
                log.info("Success (simplified prompt) with model: %s", model)
                return result
            except Exception as e:
                log.warning("Model %s simplified retry failed: %s", model, str(e)[:120])
                last_exc = e
                continue
        except Exception as e:
            log.warning("Model %s unexpected error: %s", model, str(e)[:120])
            last_exc = e
            continue
    raise last_exc


def score_all_answers(
    api_key: str,
    interview_context: dict,
    questions_and_answers: list,
) -> dict:
    candidate_name = interview_context["candidate_name"]
    role = interview_context["role"]
    role_desc = interview_context["role_desc"]
    experience_label = interview_context["experience_label"]

    qa_blocks = []
    for i, qa in enumerate(questions_and_answers):
        points = "\n".join(f"    - {p}" for p in qa.get("expected_answer_points", []))
        answer = qa.get("answer_text") or "(no answer provided)"
        qa_blocks.append(
            f"--- Q{i+1} [{qa['type']} | {qa['category']}] ---\n"
            f"Question: {qa['text']}\n"
            f"Expected key points:\n{points}\n"
            f"Candidate's answer: {answer}"
        )

    system_prompt = (
        "You are a senior hiring manager scoring a completed technical interview. "
        "Always respond with a valid JSON object only — no markdown, no prose outside the JSON."
    )

    user_prompt = f"""Score the following completed interview.

Candidate: {candidate_name}
Role: {role} — {role_desc}
Experience: {experience_label}

{chr(10).join(qa_blocks)}

Scoring rubric (score, integer 0–5):
0 — No answer or completely irrelevant
1 — Minimal understanding, major misconceptions
2 — Some basic understanding, significant gaps
3 — Covers basics adequately, some depth missing
4 — Covers most key points well, minor gaps
5 — Comprehensive, insightful, demonstrates clear mastery

Communication clarity (0.0–5.0): logical structure, technical vocabulary, clarity.

Recommendation thresholds:
- "strong_hire": average score >= 4.0 AND no score < 2
- "hire":        average score >= 3.0 AND no score < 1
- "hold":        average score >= 2.0
- "no_hire":     average score < 2.0 OR three or more scores of 0

Return this JSON object only:
{{
  "scores": [
    {{
      "order_index": 0,
      "score": <integer 0-5>,
      "feedback": "<2-3 sentences of specific, constructive feedback>",
      "communication_clarity": <float 0.0-5.0>
    }}
  ],
  "overall_summary": "<3-5 sentence narrative of the candidate's overall performance>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "areas_for_improvement": ["<area 1>", "<area 2>"],
  "recommendation": "strong_hire or hire or hold or no_hire"
}}

The scores array must have exactly {len(questions_and_answers)} entries with order_index 0 to {len(questions_and_answers)-1}."""

    last_exc: Exception = None
    for model in LLM_MODELS:
        try:
            client = get_client(api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return _extract_json_object(response.choices[0].message.content)
        except APIError as e:
            last_exc = e
            continue
    raise last_exc
