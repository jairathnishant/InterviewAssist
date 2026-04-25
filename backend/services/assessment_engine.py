import os
import json
from typing import List, Dict, Any
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def assess_answer(
    question_text: str,
    question_type: str,
    expected_points: List[str],
    transcript: str,
    code_submission: str = "",
) -> Dict[str, Any]:
    answer_content = transcript or ""
    if code_submission:
        answer_content += f"\n\nCode submitted:\n```\n{code_submission}\n```"

    if not answer_content.strip():
        return {
            "score": 0,
            "feedback": "No answer was provided.",
            "communication_clarity": 0,
            "key_points_covered": [],
            "key_points_missed": expected_points,
        }

    prompt = f"""You are an expert technical interviewer assessing a candidate's answer.

Question Type: {question_type}
Question: {question_text}

Expected Key Points to Cover:
{json.dumps(expected_points, indent=2)}

Candidate's Answer:
{answer_content}

Assess the answer and return a JSON object with these exact fields:
{{
  "score": <integer 0-5>,
  "feedback": "<2-3 sentences of specific, constructive feedback>",
  "communication_clarity": <float 0.0-5.0>,
  "key_points_covered": ["point that was covered", ...],
  "key_points_missed": ["point that was missed or incomplete", ...]
}}

Scoring rubric (score field):
- 0: No relevant answer or completely incorrect
- 1: Very poor - shows minimal understanding, major misconceptions
- 2: Below average - some basic understanding but significant gaps
- 3: Average - covers basics adequately, some depth missing
- 4: Good - covers most key points well, minor gaps
- 5: Excellent - comprehensive, insightful, demonstrates clear mastery

Communication clarity (0-5):
- Coherence and logical structure of the response
- Appropriate use of technical vocabulary
- Clarity of explanation for complex concepts

For coding questions, also assess code correctness, efficiency, and edge case handling.
Return only valid JSON, no extra text."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text
    start = content.find("{")
    end = content.rfind("}") + 1
    result = json.loads(content[start:end])

    result["score"] = max(0, min(5, int(result.get("score", 0))))
    result["communication_clarity"] = max(0.0, min(5.0, float(result.get("communication_clarity", 0))))
    return result


def generate_final_assessment(
    candidate_name: str,
    role: str,
    answers: List[Dict[str, Any]],
    proctoring_events: List[Dict[str, Any]],
    integrity_score: float,
) -> Dict[str, Any]:
    qa_summary = "\n".join(
        f"Q{i+1} ({a['type']}): Score {a['score']}/5 - {a['feedback'][:100]}"
        for i, a in enumerate(answers)
    )

    high_severity_events = [e for e in proctoring_events if e.get("severity") == "high"]
    fraud_summary = f"{len(proctoring_events)} total events, {len(high_severity_events)} high-severity"

    prompt = f"""You are an expert hiring manager reviewing a completed technical interview.

Candidate: {candidate_name}
Role: {role}
Integrity Score: {integrity_score:.1f}/5.0 (based on proctoring analysis)
Fraud Alerts: {fraud_summary}

Question-by-Question Performance:
{qa_summary}

Based on this data, provide a final hiring recommendation:

Return a JSON object:
{{
  "final_decision": "selected" | "rejected" | "hold",
  "decision_reason": "<2-3 sentence explanation of the decision>",
  "strengths": ["strength1", "strength2", ...],
  "areas_for_improvement": ["area1", "area2", ...]
}}

Decision criteria:
- "selected": Overall strong performance (avg score ≥ 3.5) AND integrity score ≥ 3.5
- "rejected": Poor performance (avg score < 2.5) OR critical integrity issues (integrity < 2.0)
- "hold": Mixed performance or minor integrity concerns - needs further evaluation

Return only valid JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end])
