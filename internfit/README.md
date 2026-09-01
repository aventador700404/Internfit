# InternFit

InternFit is a transparent internship-application prioritizer.

Upload a `.docx` CV once, paste a public job-posting URL, and receive:

- a 0-100 fit score and S/A/B/C grade;
- eligibility warnings before a high score becomes misleading;
- matched CV evidence and missing requirements;
- an application-priority recommendation.

## Design principle

The language model or parser may extract text, but the score is calculated by a visible rule set. This makes the score explainable and lets users audit why a job was ranked.

## Run locally

```bash
python -m pip install -r requirements.txt
python ../internfit_web/server.py 8000
```

Then open `http://127.0.0.1:8000`. The web screen sends the uploaded `.docx` and job URL to `/api/analyze`; the server parses both and returns the explainable fit result. The earlier Streamlit prototype remains available with `streamlit run app.py`.

## Current v0.1 limitations

- `.docx` is supported first; PDF support is next.
- A public job page is fetched with a standard request. Login walls and anti-bot pages intentionally fall back to pasting the job description.
- The scorer is calibrated against three live September 2026 public postings: SAP (expected high fit), ING DCM (mid fit), and RLWRLD Japanese (eligibility fail).
