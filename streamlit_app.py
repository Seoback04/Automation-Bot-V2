from __future__ import annotations

import json

import streamlit as st

from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.controller import AutomationController
from jobbot.config.manager import ConfigManager
from jobbot.config.models import AppSettings, EmploymentRecord, ProfileData


st.set_page_config(page_title="JobBot Local Automation", layout="wide")

config_manager = ConfigManager()

if "controller" not in st.session_state:
    st.session_state.controller = None
if "run_snapshot" not in st.session_state:
    st.session_state.run_snapshot = config_manager.latest_run_snapshot()

settings = config_manager.load_settings()
profile = config_manager.load_profile()

st.title("JobBot Local Automation")
st.caption(
    "Local-first job application automation with Streamlit, Playwright, Selenium fallback, "
    "and Ollama-generated content. Dry-run is enabled by default for safety."
)

tab_profile, tab_settings, tab_run, tab_content = st.tabs(
    ["Profile", "Settings", "Automation", "Logs & Content"]
)

with tab_profile:
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        full_name = col1.text_input("Full name", value=profile.full_name)
        email = col2.text_input("Email", value=profile.email)
        phone = col1.text_input("Phone", value=profile.phone)
        location = col2.text_input("Location", value=profile.location)
        linkedin_url = col1.text_input("LinkedIn URL", value=profile.linkedin_url)
        portfolio_url = col2.text_input("Portfolio URL", value=profile.portfolio_url)
        summary = st.text_area("Professional summary", value=profile.summary, height=120)
        skills_text = st.text_area("Skills (one per line)", value="\n".join(profile.skills), height=120)
        work_authorization = col1.text_input("Work authorization", value=profile.work_authorization)
        remote_preference = col2.text_input("Remote preference", value=profile.remote_preference)
        salary_expectation = col1.text_input("Salary expectation", value=profile.salary_expectation)
        notice_period = col2.text_input("Notice period", value=profile.notice_period)
        custom_answers_text = st.text_area(
            "Custom answers JSON",
            value=json.dumps(profile.custom_answers, indent=2),
            height=160,
        )
        employment_text = st.text_area(
            "Employment history JSON",
            value=json.dumps([record.__dict__ for record in profile.employment], indent=2),
            height=200,
        )
        save_profile_clicked = st.form_submit_button("Save Profile")

    if save_profile_clicked:
        try:
            parsed_answers = json.loads(custom_answers_text or "{}")
            parsed_employment = json.loads(employment_text or "[]")
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
                custom_answers=parsed_answers,
                employment=[EmploymentRecord.from_dict(item) for item in parsed_employment],
                education=profile.education,
            )
            config_manager.save_profile(new_profile)
            st.success("Profile saved.")
        except json.JSONDecodeError as exc:
            st.error(f"Could not parse JSON fields: {exc}")

with tab_settings:
    with st.form("settings_form"):
        col1, col2 = st.columns(2)
        browser_binary_path = col1.text_input("Brave/Chrome binary path", value=settings.browser.browser_binary_path)
        browser_user_data_dir = col2.text_input("Browser user data dir", value=settings.browser.browser_user_data_dir)
        headless = col1.checkbox("Headless", value=settings.browser.headless)
        timeout_ms = col2.number_input("Timeout (ms)", min_value=3000, value=settings.browser.timeout_ms, step=1000)
        slow_mo_ms = col1.number_input("Slow motion (ms)", min_value=0, value=settings.browser.slow_mo_ms, step=50)
        screenshot_on_failure = col2.checkbox("Screenshots on failure", value=settings.browser.screenshot_on_failure)
        ollama_enabled = col1.checkbox("Enable Ollama", value=settings.ollama.enabled)
        ollama_base_url = col2.text_input("Ollama base URL", value=settings.ollama.base_url)
        ollama_model = col1.text_input("Ollama model", value=settings.ollama.model)
        request_timeout_seconds = col2.number_input(
            "Ollama timeout (s)",
            min_value=10,
            value=settings.ollama.request_timeout_seconds,
            step=5,
        )
        resume_file = st.file_uploader("Upload resume PDF", type=["pdf"])
        resume_path = st.text_input("Current resume path", value=settings.resume_path or config_manager.resolve_resume_path())
        save_settings_clicked = st.form_submit_button("Save Settings")

    if save_settings_clicked:
        new_settings = AppSettings.from_dict(settings.to_dict())
        new_settings.browser.browser_binary_path = browser_binary_path
        new_settings.browser.browser_user_data_dir = browser_user_data_dir
        new_settings.browser.headless = headless
        new_settings.browser.timeout_ms = int(timeout_ms)
        new_settings.browser.slow_mo_ms = int(slow_mo_ms)
        new_settings.browser.screenshot_on_failure = screenshot_on_failure
        new_settings.ollama.enabled = ollama_enabled
        new_settings.ollama.base_url = ollama_base_url
        new_settings.ollama.model = ollama_model
        new_settings.ollama.request_timeout_seconds = int(request_timeout_seconds)
        new_settings.resume_path = resume_path

        if resume_file is not None:
            new_settings.resume_path = config_manager.save_resume_bytes(resume_file.name, resume_file.getvalue())

        config_manager.save_settings(new_settings)
        st.success(f"Settings saved. Resume path: {new_settings.resume_path or 'Not set'}")

    health_ok, health_message = OllamaClient(config_manager.load_settings().ollama).healthcheck()
    if health_ok:
        st.caption(f"Ollama: {health_message}")
    else:
        st.warning(health_message)
    st.caption(f"Stored resume: `{config_manager.resolve_resume_path() or 'No resume uploaded yet'}`")

with tab_run:
    current_settings = config_manager.load_settings()
    current_snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
    site_options = ["linkedin", "seek"]
    engine_options = ["playwright", "selenium"]

    with st.form("run_form"):
        col1, col2, col3 = st.columns(3)
        site = col1.selectbox(
            "Job site",
            options=site_options,
            index=site_options.index(current_settings.run.site) if current_settings.run.site in site_options else 0,
        )
        query = col2.text_input("Job title / keywords", value=current_settings.run.query)
        location = col3.text_input("Location", value=current_settings.run.location)
        primary_engine = col1.selectbox(
            "Primary engine",
            options=engine_options,
            index=engine_options.index(current_settings.run.primary_engine)
            if current_settings.run.primary_engine in engine_options
            else 0,
        )
        fallback_engine = col2.selectbox(
            "Fallback engine",
            options=engine_options,
            index=engine_options.index(current_settings.run.fallback_engine)
            if current_settings.run.fallback_engine in engine_options
            else 1,
        )
        max_jobs = col3.number_input("Max jobs", min_value=1, max_value=20, value=current_settings.run.max_jobs)
        dry_run = col1.checkbox("Dry run", value=current_settings.run.dry_run)
        stop_before_submit = col2.checkbox("Stop before submit", value=current_settings.run.stop_before_submit)
        stop_on_captcha = col3.checkbox("Stop on CAPTCHA", value=current_settings.run.stop_on_captcha)
        auto_generate_cover_letter = col1.checkbox(
            "Generate cover letters",
            value=current_settings.run.auto_generate_cover_letter,
        )
        auto_answer_screening_questions = col2.checkbox(
            "Answer screening questions",
            value=current_settings.run.auto_answer_screening_questions,
        )
        start_clicked = st.form_submit_button("Start Automation")

    col_start, col_continue, col_stop = st.columns(3)
    continue_clicked = col_continue.button("Continue Past Checkpoint", use_container_width=True)
    stop_clicked = col_stop.button("Stop Run", use_container_width=True)

    if start_clicked:
        controller = AutomationController(config_manager)
        st.session_state.controller = controller
        st.session_state.run_snapshot = controller.start(
            {
                "run": {
                    "site": site,
                    "query": query,
                    "location": location,
                    "primary_engine": primary_engine,
                    "fallback_engine": fallback_engine,
                    "max_jobs": int(max_jobs),
                    "dry_run": dry_run,
                    "stop_before_submit": stop_before_submit,
                    "stop_on_captcha": stop_on_captcha,
                    "auto_generate_cover_letter": auto_generate_cover_letter,
                    "auto_answer_screening_questions": auto_answer_screening_questions,
                }
            }
        )
        st.rerun()

    if continue_clicked and st.session_state.controller is not None:
        st.session_state.run_snapshot = st.session_state.controller.resume()
        st.rerun()

    if stop_clicked and st.session_state.controller is not None:
        st.session_state.run_snapshot = st.session_state.controller.stop()
        st.session_state.controller = None
        st.rerun()

    snapshot = st.session_state.run_snapshot or current_snapshot
    if snapshot:
        st.subheader("Run Status")
        st.json(snapshot)

        checkpoint = snapshot.get("pending_checkpoint")
        if checkpoint:
            st.warning(checkpoint.get("message", "Manual checkpoint waiting."))
        elif snapshot.get("status") == "completed":
            st.success("Run completed.")
        elif snapshot.get("status") == "failed":
            st.error(snapshot.get("last_error", "Run failed."))
    else:
        st.info("No run has been started yet.")

with tab_content:
    latest_snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
    latest_logs = config_manager.latest_log_text()
    latest_assets = config_manager.latest_generated_assets()

    st.subheader("Latest Snapshot")
    if latest_snapshot:
        st.json(latest_snapshot)
    else:
        st.info("No run snapshot found yet.")

    st.subheader("Generated Content")
    if latest_assets:
        selected_asset = st.selectbox("Artifact", options=list(latest_assets.keys()))
        st.code(latest_assets[selected_asset], language="markdown")
    else:
        st.info("No generated content yet.")

    st.subheader("Logs")
    if latest_logs:
        st.code(latest_logs, language="text")
    else:
        st.info("No logs yet.")
