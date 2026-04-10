# JobBot Local Automation

Local-first Windows job application automation with a Streamlit control panel, Playwright as the primary engine, Selenium as a compatibility fallback, and Ollama for tailored content generation.

## Features

- Streamlit UI for profile editing, resume upload, run configuration, automation control, logs, and generated content.
- JSON-backed local config in `data/config/profile.json` and `data/config/settings.json`.
- Playwright-first browser automation for Brave or Chrome with Selenium fallback.
- Site adapters for LinkedIn and Seek with reusable controller-driven workflows.
- Human checkpoints for manual login, CAPTCHA handling, and final review.
- Safe defaults: dry-run enabled and stop-before-submit enabled.
- Local Ollama integration for job analysis, cover letters, and screening-question drafts.
- Run artifacts stored under `data/runs/<timestamp>/` with logs, screenshots, and generated markdown.

## Run It

1. Create or activate your virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
playwright install chromium
```

3. Start the UI in VS Code terminal:

```powershell
streamlit run streamlit_app.py
```

4. Open the browser shown by Streamlit, save your profile, upload a PDF resume, and start a dry-run.

## Project Layout

```text
jobbot/
  adapters/              Site-specific automation logic
  ai/                    Ollama HTTP client
  automation/            Workflow controller and browser engines
  config/                Dataclass models and JSON persistence
  utils/                 Logging, retry, and path helpers
streamlit_app.py         Main local UI
tools/job_apply.py       Optional console runner with checkpoints
data/config/             Local profile/settings JSON files
data/runs/               Run logs, screenshots, generated content
```

## Notes

- Keep `dry_run` on until you trust a workflow on a specific site.
- Use a dedicated browser profile directory for automation sessions.
- Many job sites change markup often, so adapters are intentionally modular and selector lists are easy to expand.
- Local resumes, generated artifacts, browser state, and run logs are intentionally git-ignored.
