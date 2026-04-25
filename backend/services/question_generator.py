import os
import json
from typing import List, Dict, Any
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ROLE_DESCRIPTIONS = {
    "data_engineer": "Data Engineer specializing in ETL/ELT pipelines, data warehousing, SQL, Python, Apache Spark, cloud data platforms (AWS/Azure/GCP), orchestration tools like Airflow, and data quality.",
    "data_scientist": "Data Scientist specializing in machine learning, statistical analysis, Python, R, model building and deployment, A/B testing, feature engineering, and data storytelling.",
    "pbi_developer": "Power BI Developer specializing in data visualization, DAX formulas, Power Query (M language), data modeling, report design, and connecting to various data sources.",
    "ml_engineer": "Machine Learning Engineer specializing in ML infrastructure, model training pipelines, MLOps, model serving, monitoring, and scalable deployment on cloud platforms.",
    "software_engineer": "Software Engineer specializing in system design, algorithms, data structures, API development, distributed systems, and software architecture.",
    "data_analyst": "Data Analyst specializing in SQL, Excel, data visualization tools, statistical analysis, business intelligence, and translating data insights into business decisions.",
}

EXPERIENCE_LEVELS = {
    range(0, 2): "entry-level (0-1 years)",
    range(2, 5): "mid-level (2-4 years)",
    range(5, 8): "senior (5-7 years)",
    range(8, 100): "principal/lead (8+ years)",
}


def get_experience_label(years: int) -> str:
    for r, label in EXPERIENCE_LEVELS.items():
        if years in r:
            return label
    return "experienced"


def generate_questions(
    role: str,
    experience_years: int,
    skills: List[str],
    projects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    role_desc = ROLE_DESCRIPTIONS.get(role, role.replace("_", " ").title())
    exp_label = get_experience_label(experience_years)

    projects_text = json.dumps(projects[:4], indent=2) if projects else "No projects provided"
    skills_text = ", ".join(skills[:20]) if skills else "Not specified"

    prompt = f"""You are an expert technical interviewer. Generate a complete interview question set for a {role_desc} position.

Candidate Level: {exp_label} ({experience_years} years)
Candidate Skills: {skills_text}

Candidate Projects:
{projects_text}

Generate exactly 9 questions in this order:
1. Technical question 1 (core role concept)
2. Technical question 2 (tools/technologies from their skill set)
3. Technical question 3 (scenario/problem-solving for role)
4. Technical question 4 (advanced concept appropriate for experience level)
5. Project-based question 1 (reference a specific project from resume)
6. Project-based question 2 (reference another project or dive deeper)
7. Behavioral question 1 (challenge or conflict resolution)
8. Behavioral question 2 (teamwork, communication, or leadership)
9. Coding challenge (solvable in 8-10 minutes, appropriate difficulty for experience level)

Calibrate difficulty to {exp_label}:
- Entry: fundamentals, basic implementations
- Mid: optimization, design decisions, intermediate algorithms
- Senior: system design, complex problem solving, architectural trade-offs
- Principal: leadership, large-scale systems, mentoring scenarios

Return a JSON array with exactly 9 objects. Each object must have:
{{
  "type": "technical" | "project" | "behavioral" | "coding",
  "category": "specific skill/area being tested",
  "text": "the complete question text",
  "expected_answer_points": ["key point 1", "key point 2", "key point 3"],
  "time_limit_seconds": <integer between 120 and 600>,
  "starter_code": "<initial code template for coding questions, empty string otherwise>",
  "test_cases": [
    {{"input": "...", "expected_output": "..."}}
  ]
}}

For non-coding questions, starter_code must be "" and test_cases must be [].
For coding questions, provide 2-3 test cases.
Return only valid JSON array, no extra text."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text
    start = content.find("[")
    end = content.rfind("]") + 1
    questions = json.loads(content[start:end])

    for i, q in enumerate(questions):
        q.setdefault("starter_code", "")
        q.setdefault("test_cases", [])
        q.setdefault("time_limit_seconds", 180)
        q["order_index"] = i

    return questions
