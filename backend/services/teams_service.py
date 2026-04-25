import os
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

import httpx
import msal


def _get_access_token() -> str:
    authority = f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}"
    app = msal.ConfidentialClientApplication(
        client_id=os.getenv("AZURE_CLIENT_ID"),
        client_credential=os.getenv("AZURE_CLIENT_SECRET"),
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Token acquisition failed: {result.get('error_description', 'unknown error')}")
    return result["access_token"]


def create_teams_meeting(
    subject: str,
    start_time: Optional[datetime] = None,
    duration_minutes: int = 60,
) -> Dict[str, Any]:
    if start_time is None:
        start_time = datetime.utcnow() + timedelta(hours=1)
    end_time = start_time + timedelta(minutes=duration_minutes)

    token = _get_access_token()
    user_id = os.getenv("TEAMS_USER_ID")

    body = {
        "subject": subject,
        "startDateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "endDateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
    }

    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/onlineMeetings"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    return {
        "meeting_id": data.get("id", ""),
        "join_url": data.get("joinWebUrl", ""),
    }


def send_interview_invite(
    candidate_email: str,
    candidate_name: str,
    interview_link: str,
    teams_link: str,
    role: str,
) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Interview Invitation – {role.replace('_', ' ').title()} Role"
    msg["From"] = smtp_user
    msg["To"] = candidate_email

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: #2563EB; padding: 24px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: white; margin: 0; font-size: 24px;">InterviewAssist</h1>
  </div>
  <div style="border: 1px solid #e5e7eb; border-top: none; padding: 32px; border-radius: 0 0 8px 8px;">
    <h2 style="color: #1f2937;">Interview Invitation</h2>
    <p>Dear <strong>{candidate_name}</strong>,</p>
    <p>You have been invited to complete a technical interview for the <strong>{role.replace('_', ' ').title()}</strong> position.</p>

    <div style="background: #f0f9ff; border-left: 4px solid #2563EB; padding: 16px; margin: 24px 0; border-radius: 4px;">
      <p style="margin: 0 0 12px 0;"><strong>Option 1 – Complete your interview online:</strong></p>
      <a href="{interview_link}" style="background: #2563EB; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
        Start Interview
      </a>
    </div>

    <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 16px; margin: 24px 0; border-radius: 4px;">
      <p style="margin: 0 0 12px 0;"><strong>Option 2 – Join via Microsoft Teams:</strong></p>
      <a href="{teams_link}" style="color: #16a34a; word-break: break-all;">{teams_link}</a>
    </div>

    <h3 style="color: #374151;">Before you begin, please ensure:</h3>
    <ul style="color: #6b7280;">
      <li>Your webcam and microphone are working</li>
      <li>You are in a quiet, well-lit environment</li>
      <li>You have a stable internet connection</li>
      <li>You allow camera and microphone permissions in your browser</li>
      <li>You have approximately 40 minutes available</li>
    </ul>

    <p style="color: #9ca3af; font-size: 14px;">This interview is AI-proctored. Please complete it honestly and independently.</p>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
