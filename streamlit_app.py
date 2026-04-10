from __future__ import annotations

import json

import streamlit as st

from jobbot.adapters.registry import supported_site_names
from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.controller import AutomationController
from jobbot.config.manager import ConfigManager
from jobbot.config.models import AppSettings, EducationRecord, EmploymentRecord, ProfileData
from jobbot.utils.browser_probe import probe_remote_browser


st.set_page_config(page_title="JobBot Local Control", page_icon=":briefcase:", layout="wide")

config_manager = ConfigManager()

if "controller" not in st.session_state:
    st.session_state.controller = None
if "run_snapshot" not in st.session_state:
    st.session_state.run_snapshot = config_manager.latest_run_snapshot()

settings = config_manager.load_settings()
profile = config_manager.load_profile()
snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
ollama_client = OllamaClient(settings.ollama)
ollama_ok, ollama_message = ollama_client.healthcheck()
attach_ok, attach_message, attach_payload = probe_remote_browser(settings.browser.remote_debugging_url)
site_options = supported_site_names()

st.markdown(
    """
    <style>
    .card {
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        background: linear-gradient(180deg, rgba(248,249,251,0.9), rgba(240,244,248,0.85));
        margin-bottom: 0.75rem;
    }
    .metric {
        font-size: 1.7rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .muted {
        color: #5c6470;
        font-size: 0.92rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def canonical_site(value: str) -> str:
    alias_map = {"student job search": "student_job_search", "sjs": "student_job_search", "zeal": "zeil"}
    return alias_map.get(value, value)


def site_index(current_value: str) -> int:
    normalized = canonical_site(current_value)
    return site_options.index(normalized) if normalized in site_options else 0


def parse_json_records(raw_text: str) -> list[dict]:
    value = json.loads(raw_text or "[]")
    return value if isinstance(value, list) else []


def render_metric_card(title: str, value: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="card">
            <div class="muted">{title}</div>
            <div class="metric">{value}</div>
            <div class="muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.title("JobBot")
    st.caption("Interactive local automation console")

    render_metric_card(
        "Run Status",
        str(snapshot.get("status", "idle")).replace("_", " ").title() if snapshot else "Idle",
        snapshot.get("stage", "Waiting to start").replace("_", " ").title() if snapshot else "Waiting to start",
    )
    render_metric_card(
        "Resume",
        "Ready" if config_manager.resolve_resume_path() else "Missing",
        config_manager.resolve_resume_path() or "Upload a PDF in the setup tab",
    )
    render_metric_card(
        "Ollama",
        "Online" if ollama_ok else "Offline",
        ollama_message,
    )
    render_metric_card(
        "Brave Attach",
        "Ready" if attach_ok else "Unavailable",
        attach_message,
    )

    st.markdown("**Supported Sites**")
    st.caption(", ".join(site_options))
    st.markdown("**Attach Note**")
    st.caption(
        "Attaching to the same already-open Brave window only works when Brave was started with remote debugging enabled, "
        "for example `--remote-debugging-port=9222`."
    )

st.title("JobBot Local Control Panel")
st.caption(
    "Streamlit dashboard for local-first job application automation with Playwright, Selenium fallback, "
    "Ollama drafting, human checkpoints, and safe dry-run defaults."
)

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
with summary_col1:
    render_metric_card("Processed Jobs", str(len(snapshot.get("job_results", [])) if snapshot else 0), "Jobs reviewed in this run")
with summary_col2:
    render_metric_card("Queued Jobs", str(len(snapshot.get("job_links", [])) if snapshot else 0), "Detected or manually supplied URLs")
with summary_col3:
    render_metric_card("Current Page", snapshot.get("current_title", "N/A") if snapshot else "N/A", snapshot.get("current_url", "") if snapshot else "")
with summary_col4:
    render_metric_card("Safety Mode", "Dry Run" if settings.run.dry_run else "Live", "Stops before submit when enabled")

tab_dashboard, tab_profile, tab_setup, tab_live, tab_artifacts = st.tabs(
    ["Dashboard", "Profile", "Run Setup", "Live Run", "Artifacts"]
)

with tab_dashboard:
    col_left, col_right = st.columns([1.2, 1])
    with col_left:
        st.subheader("Readiness")
        checklist = [
            ("Profile saved", bool(profile.full_name and profile.email)),
            ("Resume available", bool(config_manager.resolve_resume_path())),
            ("Ollama reachable or disabled", bool(ollama_ok or not settings.ollama.enabled)),
            (
                "Browser attach reachable",
                bool(attach_ok or not settings.browser.attach_to_existing_browser),
            ),
        ]
        for label, ok in checklist:
            if ok:
                st.success(label)
            else:
                st.warning(label)

        st.subheader("Current Run")
        if snapshot:
            st.progress(float(snapshot.get("progress_ratio", 0.0)))
            st.json(
                {
                    "status": snapshot.get("status"),
                    "stage": snapshot.get("stage"),
                    "site": snapshot.get("site"),
                    "query": snapshot.get("query"),
                    "location": snapshot.get("location"),
                    "current_url": snapshot.get("current_url"),
                }
            )
        else:
            st.info("No run has been started yet.")

    with col_right:
        st.subheader("Attach Monitor")
        if settings.browser.attach_to_existing_browser:
            if attach_ok:
                st.success(attach_message)
                if attach_payload:
                    st.code(json.dumps(attach_payload, indent=2), language="json")
            else:
                st.error(attach_message)
                st.code(
                    f'"{settings.browser.browser_binary_path}" --remote-debugging-port=9222',
                    language="powershell",
                )
        else:
            st.info("Attach mode is currently off. Enable it in Run Setup to reuse an existing Brave session.")

        st.subheader("Recommended Workflow")
        st.markdown(
            "\n".join(
                [
                    "1. Enable attach mode if you want to reuse the current Brave session.",
                    "2. Open the target job site or paste direct job URLs.",
                    "3. Keep dry-run on until a workflow behaves reliably.",
                    "4. Use the Live Run tab to start, resume checkpoints, and inspect results.",
                ]
            )
        )

with tab_profile:
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        full_name = col1.text_input("Full name", value=profile.full_name)
        email = col2.text_input("Email", value=profile.email)
        phone = col1.text_input("Phone", value=profile.phone)
        location = col2.text_input("Location", value=profile.location)
        linkedin_url = col1.text_input("LinkedIn URL", value=profile.linkedin_url)
        portfolio_url = col2.text_input("Portfolio or website", value=profile.portfolio_url)
        summary = st.text_area("Professional summary", value=profile.summary, height=140)
        skills_text = st.text_area("Skills", value="\n".join(profile.skills), height=140)
        work_authorization = col1.text_input("Work authorization", value=profile.work_authorization)
        remote_preference = col2.text_input("Remote preference", value=profile.remote_preference)
        salary_expectation = col1.text_input("Salary expectation", value=profile.salary_expectation)
        notice_period = col2.text_input("Notice period / availability", value=profile.notice_period)
        custom_answers_text = st.text_area(
            "Custom answers JSON",
            value=json.dumps(profile.custom_answers, indent=2),
            height=180,
        )
        employment_text = st.text_area(
            "Employment history JSON",
            value=json.dumps([record.__dict__ for record in profile.employment], indent=2),
            height=180,
        )
        education_text = st.text_area(
            "Education history JSON",
            value=json.dumps([record.__dict__ for record in profile.education], indent=2),
            height=160,
        )
        save_profile_clicked = st.form_submit_button("Save Profile")

    if save_profile_clicked:
        try:
            new_profile = ProfileData(
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                linkedin_url=linkedin_url,
                portfolio_url=portfolio_url,
                summary=summary,
                skills=[line.strip() for line in skills_text.splitlines() if line.strip()],
                work_authorization=work_authorization,
                remote_preference=remote_preference,
                salary_expectation=salary_expectation,
                notice_period=notice_period,
                custom_answers=json.loads(custom_answers_text or "{}"),
                employment=[EmploymentRecord.from_dict(item) for item in parse_json_records(employment_text)],
                education=[EducationRecord.from_dict(item) for item in parse_json_records(education_text)],
            )
            config_manager.save_profile(new_profile)
            st.success("Profile saved.")
        except json.JSONDecodeError as exc:
            st.error(f"Could not parse the JSON sections: {exc}")

with tab_setup:
    st.subheader("Browser, AI, and Run Configuration")
    with st.form("settings_form"):
        bcol1, bcol2, bcol3 = st.columns(3)
        browser_binary_path = bcol1.text_input("Brave/Chrome binary path", value=settings.browser.browser_binary_path)
        browser_user_data_dir = bcol2.text_input("Browser user data dir", value=settings.browser.browser_user_data_dir)
        remote_debugging_url = bcol3.text_input("Remote debugging URL", value=settings.browser.remote_debugging_url)
        attach_to_existing_browser = bcol1.checkbox("Attach to existing Brave/Chrome", value=settings.browser.attach_to_existing_browser)
        reuse_current_page_on_attach = bcol2.checkbox("Reuse current page when attached", value=settings.browser.reuse_current_page_on_attach)
        keep_browser_open = bcol3.checkbox("Keep browser open after run", value=settings.browser.keep_browser_open)
        headless = bcol1.checkbox("Headless", value=settings.browser.headless)
        timeout_ms = bcol2.number_input("Timeout (ms)", min_value=3000, value=settings.browser.timeout_ms, step=1000)
        slow_mo_ms = bcol3.number_input("Slow motion (ms)", min_value=0, value=settings.browser.slow_mo_ms, step=50)
        screenshot_on_failure = bcol1.checkbox("Screenshots on failure", value=settings.browser.screenshot_on_failure)

        ocol1, ocol2, ocol3 = st.columns(3)
        ollama_enabled = ocol1.checkbox("Enable Ollama", value=settings.ollama.enabled)
        ollama_base_url = ocol2.text_input("Ollama base URL", value=settings.ollama.base_url)
        ollama_model = ocol3.text_input("Ollama model", value=settings.ollama.model)
        request_timeout_seconds = ocol2.number_input(
            "Ollama timeout (seconds)",
            min_value=10,
            value=settings.ollama.request_timeout_seconds,
            step=5,
        )

        resume_file = st.file_uploader("Upload resume PDF", type=["pdf"])
        resume_path = st.text_input("Current resume path", value=settings.resume_path or config_manager.resolve_resume_path())

        rcol1, rcol2, rcol3 = st.columns(3)
        site = rcol1.selectbox("Site adapter", options=site_options, index=site_index(settings.run.site))
        query = rcol2.text_input("Job title / keywords", value=settings.run.query)
        location = rcol3.text_input("Location", value=settings.run.location)
        start_url = rcol1.text_input("Start URL", value=settings.run.start_url)
        primary_engine = rcol2.selectbox(
            "Primary engine",
            options=["playwright", "selenium"],
            index=0 if settings.run.primary_engine == "playwright" else 1,
        )
        fallback_engine = rcol3.selectbox(
            "Fallback engine",
            options=["selenium", "playwright"],
            index=0 if settings.run.fallback_engine == "selenium" else 1,
        )
        max_jobs = rcol1.number_input("Max jobs", min_value=1, max_value=30, value=settings.run.max_jobs)
        dry_run = rcol2.checkbox("Dry run", value=settings.run.dry_run)
        stop_before_submit = rcol3.checkbox("Stop before submit", value=settings.run.stop_before_submit)
        stop_on_captcha = rcol1.checkbox("Stop on CAPTCHA", value=settings.run.stop_on_captcha)
        auto_generate_cover_letter = rcol2.checkbox("Generate cover letters", value=settings.run.auto_generate_cover_letter)
        auto_answer_screening_questions = rcol3.checkbox(
            "Answer screening questions",
            value=settings.run.auto_answer_screening_questions,
        )
        auto_fill_generic_forms = rcol1.checkbox("Generic form fill mode", value=settings.run.auto_fill_generic_forms)
        job_urls_text = st.text_area(
            "Direct job URLs (one per line)",
            value="\n".join(settings.run.job_urls),
            height=140,
        )

        save_settings_clicked = st.form_submit_button("Save Configuration")

    if save_settings_clicked:
        new_settings = AppSettings.from_dict(settings.to_dict())
        new_settings.browser.browser_binary_path = browser_binary_path
        new_settings.browser.browser_user_data_dir = browser_user_data_dir
        new_settings.browser.remote_debugging_url = remote_debugging_url
        new_settings.browser.attach_to_existing_browser = attach_to_existing_browser
        new_settings.browser.reuse_current_page_on_attach = reuse_current_page_on_attach
        new_settings.browser.keep_browser_open = keep_browser_open
        new_settings.browser.headless = headless
        new_settings.browser.timeout_ms = int(timeout_ms)
        new_settings.browser.slow_mo_ms = int(slow_mo_ms)
        new_settings.browser.screenshot_on_failure = screenshot_on_failure
        new_settings.ollama.enabled = ollama_enabled
        new_settings.ollama.base_url = ollama_base_url
        new_settings.ollama.model = ollama_model
        new_settings.ollama.request_timeout_seconds = int(request_timeout_seconds)
        new_settings.resume_path = resume_path
        new_settings.run.site = canonical_site(site)
        new_settings.run.query = query
        new_settings.run.location = location
        new_settings.run.start_url = start_url.strip()
        new_settings.run.primary_engine = primary_engine
        new_settings.run.fallback_engine = fallback_engine
        new_settings.run.max_jobs = int(max_jobs)
        new_settings.run.dry_run = dry_run
        new_settings.run.stop_before_submit = stop_before_submit
        new_settings.run.stop_on_captcha = stop_on_captcha
        new_settings.run.auto_generate_cover_letter = auto_generate_cover_letter
        new_settings.run.auto_answer_screening_questions = auto_answer_screening_questions
        new_settings.run.auto_fill_generic_forms = auto_fill_generic_forms
        new_settings.run.job_urls = [line.strip() for line in job_urls_text.splitlines() if line.strip()]

        if resume_file is not None:
            new_settings.resume_path = config_manager.save_resume_bytes(resume_file.name, resume_file.getvalue())

        config_manager.save_settings(new_settings)
        st.success("Configuration saved.")

    if settings.browser.attach_to_existing_browser:
        if attach_ok:
            st.success("Attach mode is ready. The app can reuse the current Chromium/Brave session.")
        else:
            st.warning(
                "Attach mode is enabled, but the remote debugging endpoint is not reachable yet. "
                "Launch Brave with remote debugging before starting the run."
            )
            st.code(f'"{settings.browser.browser_binary_path}" --remote-debugging-port=9222', language="powershell")

with tab_live:
    st.subheader("Run Controls")
    current_settings = config_manager.load_settings()
    control_col1, control_col2, control_col3, control_col4 = st.columns(4)
    start_clicked = control_col1.button("Start Automation", use_container_width=True)
    continue_clicked = control_col2.button("Continue Checkpoint", use_container_width=True)
    refresh_clicked = control_col3.button("Refresh Snapshot", use_container_width=True)
    stop_clicked = control_col4.button("Stop Run", use_container_width=True)

    if start_clicked:
        controller = AutomationController(config_manager)
        st.session_state.controller = controller
        st.session_state.run_snapshot = controller.start(
            {
                "run": {
                    "site": current_settings.run.site,
                    "query": current_settings.run.query,
                    "location": current_settings.run.location,
                    "start_url": current_settings.run.start_url,
                    "job_urls": current_settings.run.job_urls,
                    "primary_engine": current_settings.run.primary_engine,
                    "fallback_engine": current_settings.run.fallback_engine,
                    "max_jobs": current_settings.run.max_jobs,
                    "dry_run": current_settings.run.dry_run,
                    "stop_before_submit": current_settings.run.stop_before_submit,
                    "stop_on_captcha": current_settings.run.stop_on_captcha,
                    "auto_generate_cover_letter": current_settings.run.auto_generate_cover_letter,
                    "auto_answer_screening_questions": current_settings.run.auto_answer_screening_questions,
                    "auto_fill_generic_forms": current_settings.run.auto_fill_generic_forms,
                },
                "browser": {
                    "attach_to_existing_browser": current_settings.browser.attach_to_existing_browser,
                    "remote_debugging_url": current_settings.browser.remote_debugging_url,
                    "reuse_current_page_on_attach": current_settings.browser.reuse_current_page_on_attach,
                    "keep_browser_open": current_settings.browser.keep_browser_open,
                },
            }
        )
        st.rerun()

    if continue_clicked and st.session_state.controller is not None:
        st.session_state.run_snapshot = st.session_state.controller.resume()
        st.rerun()

    if refresh_clicked:
        st.session_state.run_snapshot = config_manager.latest_run_snapshot()
        st.rerun()

    if stop_clicked and st.session_state.controller is not None:
        st.session_state.run_snapshot = st.session_state.controller.stop()
        st.session_state.controller = None
        st.rerun()

    live_snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
    if live_snapshot:
        st.progress(float(live_snapshot.get("progress_ratio", 0.0)))
        checkpoint = live_snapshot.get("pending_checkpoint")
        if checkpoint:
            st.warning(checkpoint.get("message", "Checkpoint waiting."))
        elif live_snapshot.get("status") == "completed":
            st.success("Run completed.")
        elif live_snapshot.get("status") == "failed":
            st.error(live_snapshot.get("last_error", "Run failed."))

        status_col1, status_col2 = st.columns([1.2, 1])
        with status_col1:
            st.json(
                {
                    "status": live_snapshot.get("status"),
                    "stage": live_snapshot.get("stage"),
                    "engine": live_snapshot.get("engine"),
                    "site": live_snapshot.get("site"),
                    "current_url": live_snapshot.get("current_url"),
                    "current_title": live_snapshot.get("current_title"),
                }
            )
        with status_col2:
            if live_snapshot.get("job_results"):
                st.dataframe(live_snapshot.get("job_results"), use_container_width=True)
            else:
                st.info("No job results recorded yet.")

        st.subheader("Live Log Tail")
        log_text = config_manager.latest_log_text()
        if log_text:
            st.code("\n".join(log_text.splitlines()[-40:]), language="text")
        else:
            st.info("No logs yet.")
    else:
        st.info("No active or previous run snapshot found.")

with tab_artifacts:
    latest_snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
    latest_logs = config_manager.latest_log_text()
    latest_assets = config_manager.latest_generated_assets()

    col_a, col_b = st.columns([1, 1.2])
    with col_a:
        st.subheader("Latest Snapshot")
        if latest_snapshot:
            st.json(latest_snapshot)
        else:
            st.info("No run snapshot found yet.")

    with col_b:
        st.subheader("Generated Content")
        if latest_assets:
            selected_asset = st.selectbox("Artifact", options=list(latest_assets.keys()))
            st.code(latest_assets[selected_asset], language="markdown")
        else:
            st.info("No generated content yet.")

    st.subheader("Full Logs")
    if latest_logs:
        st.code(latest_logs, language="text")
    else:
        st.info("No logs yet.")
