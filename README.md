# JobBot Local Automation

Local-first Windows job application automation with an interactive Streamlit control panel, Playwright as the primary engine, Selenium as a compatibility fallback, and Ollama for tailored content generation.

## Features

- Streamlit UI for profile editing, resume upload, run configuration, automation control, logs, and generated content.
- Interactive dashboard with readiness checks, live run progress, browser attach status, checkpoint handling, and artifact viewers.
- JSON-backed local config in `data/config/profile.json` and `data/config/settings.json`.
- Playwright-first browser automation for Brave or Chrome with Selenium fallback.
- Attach mode for reusing an existing Brave or Chrome session through Chromium remote debugging.
- Site adapters for LinkedIn, Seek, Indeed, Student Job Search, Sidekicker, Zeil-compatible flows, and a generic job-board adapter.
- Generic form-filling heuristics that inspect visible inputs, selects, and uploads to improve cross-site compatibility.
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

## Reuse Your Existing Brave Window

If you want automation to use the same Brave session that is already open, start Brave with Chromium remote debugging enabled:

```powershell
"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222
```

Then in the UI:

- enable `Attach to existing Brave/Chrome`
- keep the remote debugging URL as `http://127.0.0.1:9222`
- optionally enable `Reuse current page when attached`

Without remote debugging enabled, automation cannot attach to an arbitrary already-open Brave window.

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
- Multi-site compatibility is best-effort: the generic filler broadens support substantially, but job sites still change markup often and some flows will need manual review or adapter tuning.
- Local resumes, generated artifacts, browser state, and run logs are intentionally git-ignored.
