# InterviewAssist

An AI-powered async interview platform for technical roles. Interviewers set up a candidate interview in seconds and share a unique link. Candidates complete the interview on their own device at their own pace — no live session required.

---

## Features

### For Interviewers
- **Role-based question generation** — supports Data Engineer, Data Scientist, Power BI Developer, Gen AI Engineer, Business Analyst, SAS Developer, or a custom role you describe
- **Experience-calibrated difficulty** — slider from 0–20 years; questions adjust from entry-level fundamentals to senior/principal system-design depth
- **Resume-aware questions** — paste the candidate's CV and the AI tailors every question to their background
- **Batch question generation** — all 9 questions are generated in one shot when the interview starts, so there's no delay between questions for the candidate
- **Shareable candidate link** — one click to copy and send; candidates need no account or login
- **Live status polling** — the created page auto-refreshes and shows when the interview moves from Ready → In Progress → Scored
- **AI-scored results** — overall score, technical / project / behavioural breakdowns, strengths, areas for improvement, and a hiring recommendation (Strong Hire / Hire / Hold / No Hire)
- **Per-question feedback** — each answer gets a score out of 5, communication clarity rating, and specific written feedback
- **Plain-text export** — download the full results report as a `.txt` file

### For Candidates
- **9-question structured interview** — 4 technical, 2 project, 2 behavioural, 1 coding
- **Audio answers** — record your answer using your microphone; live waveform and elapsed timer shown during recording
- **2-minute recording limit per question** — auto-stops at 2:00 with a countdown warning in the last 30 seconds
- **Coding question textarea** — the coding question provides a text editor instead of the recorder so you can write pseudocode or actual code
- **Free navigation** — jump between any question using the numbered pill nav or Previous / Next buttons without losing your answers
- **Answer persistence** — recorded audio is stored in the browser (IndexedDB) so revisiting a question plays back your recording
- **30-minute countdown timer** — shown in the header; persists across questions; auto-submits when time expires
- **Early finish** — a Finish Interview button lets you submit at any point if you've answered all you can
- **Proctoring basics** — copy, paste, cut, and right-click are disabled on the interview page

---

## Question Structure

| # | Type | Focus |
|---|---|---|
| 1 | Technical | Core concepts and fundamentals |
| 2 | Technical | Specific tools and technologies |
| 3 | Technical | Scenario-based problem solving |
| 4 | Technical | Advanced concept for experience level |
| 5 | Project | A specific project from the resume |
| 6 | Project | Challenges and outcomes |
| 7 | Behavioural | Conflict or disagreement at work |
| 8 | Behavioural | Teamwork, collaboration, or leadership |
| 9 | Coding | Basic-to-intermediate problem (text/pseudocode, ~10 min) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.x, FastAPI, Uvicorn |
| Frontend | Jinja2 HTML templates, Tailwind CSS (CDN) |
| Database | SQLite (via Python `sqlite3`) |
| LLM | OpenRouter API (free-tier models with automatic fallback) |
| Audio | Browser `MediaRecorder` API + IndexedDB |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/jairathnishant/InterviewAssist.git
cd InterviewAssist
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Get an OpenRouter API key

1. Sign up at [https://openrouter.ai](https://openrouter.ai)
2. Go to **Keys** and create a new key
3. Go to **Settings → Privacy** and enable data sharing (required for free-tier models)

### 4. Configure the API key

Create a `.env` file in the project root:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 5. Run the app

```bash
python -m uvicorn main:app --reload --port 8000
```

Open your browser at **http://127.0.0.1:8000**

---

## How to Use

### Interviewer workflow

1. **Open** `http://127.0.0.1:8000`
2. **Fill in the setup form:**
   - Candidate name
   - Role (select from the list or choose *Other* and describe the role)
   - Years of experience (drag the slider)
   - Resume / background (paste the candidate's CV text)
3. **Click Create Interview** — the AI generates all 9 questions instantly
4. **Copy the candidate link** shown on the next screen and send it to the candidate (email, Slack, etc.)
5. **Monitor status** — the page polls every 10 seconds and updates when the candidate starts and finishes
6. **View Results** — once the interview is scored, click *View Results* to see the full breakdown

### Candidate workflow

1. **Open the link** sent by the interviewer
2. **Click Begin Interview** — the interview starts immediately (all questions are pre-generated)
3. **For each question:**
   - Click the **microphone button** to start recording your answer
   - Speak clearly — a live waveform and timer are shown
   - Click **Stop Recording** to finish (auto-stops at 2 minutes)
   - Listen back to your recording, then click **Submit Answer & Continue**
   - For the coding question, type your approach in the text box provided
4. **Navigate freely** — use the numbered pills at the top or the Previous / Next buttons to revisit any question
5. **Finish** — after submitting all 9 answers, your responses are automatically scored. You can also click **Finish Interview** at any point to submit early.

---

## Project Structure

```
InterviewAssist/
├── main.py              # FastAPI routes and request handlers
├── database.py          # SQLite schema and all DB functions
├── llm_service.py       # OpenRouter LLM calls (question generation + scoring)
├── requirements.txt     # Python dependencies
├── .env                 # API key (not committed)
├── interviews.db        # SQLite database (auto-created on first run)
├── audio/               # Uploaded audio files (auto-created)
├── static/
│   └── style.css        # Question type badge colours
└── templates/
    ├── base.html         # Shared layout (header, footer, Tailwind)
    ├── setup.html        # Interviewer setup form
    ├── created.html      # Candidate link + status polling
    ├── results.html      # Scores, recommendation, per-question breakdown
    ├── welcome.html      # Candidate landing page
    ├── interview.html    # Question + recorder UI
    ├── thankyou.html     # Post-submission confirmation
    └── error.html        # Generic error page
```

---

## Roadmap

- **Step 3** — Whisper transcription: convert uploaded audio to text automatically
- **Step 4** — End-to-end audio interview flow with transcript-based scoring
- **Step 5** — Tab/window switch detection and proctoring event logging
- **Step 6** — Full-screen enforcement
- **Step 7 & 8** — Webcam face detection (face absent / multiple faces) via `face-api.js`
- **Step 9** — Integrity score on the results page based on proctoring events
- **Phase 3** — Email invite with Microsoft Teams meeting link
