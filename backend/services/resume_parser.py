import os
import json
import re
from typing import Dict, List, Any
import PyPDF2
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

TECH_SKILLS = {
    "languages": ["python", "r", "sql", "scala", "java", "javascript", "typescript", "c++", "c#", "go", "rust"],
    "data_tools": ["spark", "hadoop", "kafka", "airflow", "dbt", "pandas", "numpy", "scikit-learn", "tensorflow",
                   "pytorch", "keras", "xgboost", "lightgbm"],
    "databases": ["postgresql", "mysql", "mongodb", "redis", "cassandra", "snowflake", "redshift",
                  "bigquery", "databricks", "azure synapse", "cosmos db"],
    "cloud": ["aws", "azure", "gcp", "google cloud", "s3", "ec2", "lambda", "azure data factory",
              "azure devops", "kubernetes", "docker"],
    "bi_tools": ["power bi", "tableau", "looker", "qlik", "dax", "power query", "m language"],
    "ml_concepts": ["machine learning", "deep learning", "nlp", "computer vision", "regression",
                    "classification", "clustering", "neural network", "transformer", "llm"],
}


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


def extract_text_from_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".doc", ".docx"):
        return extract_text_from_docx(file_path)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def parse_resume(file_path: str) -> Dict[str, Any]:
    text = extract_text(file_path)

    prompt = f"""Analyze this resume text and extract structured information.

Resume Text:
{text[:4000]}

Return a JSON object with exactly these fields:
{{
  "skills": ["skill1", "skill2", ...],
  "projects": [
    {{
      "name": "project name",
      "description": "brief description",
      "technologies": ["tech1", "tech2"],
      "outcome": "key result or achievement"
    }}
  ],
  "experience_summary": "brief summary of overall experience",
  "education": "highest qualification"
}}

Extract all technical skills, tools, frameworks, and platforms mentioned.
Extract up to 5 most significant projects with their technologies and outcomes.
Return only valid JSON, no extra text."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text
    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1:
        return {"skills": [], "projects": [], "experience_summary": "", "education": ""}

    parsed = json.loads(content[start:end])
    return parsed
