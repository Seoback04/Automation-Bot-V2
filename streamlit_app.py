from __future__ import annotations

import json

import streamlit as st

from jobbot.adapters.registry import supported_site_names
from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.controller import AutomationController
from jobbot.config.manager import ConfigManager
from jobbot.config.models import AppSettings, EducationRecord, EmploymentRecord, ProfileData
from jobbot.utils.browser_probe import probe_remote_browser


st.set_page_config(page_title="JobBot", page_icon=":briefcase:", layout="wide")

config_manager = ConfigManager()

if "controller" not in st.session_state:
    st.session_state.controller = None
if "run_snapshot" not in st.session_state:
    st.session_state.run_snapshot = config_manager.latest_run_snapshot()


def canonical_site(value: str) -> str:
    alias_map = {"student job search": "student_job_search", "sjs": "student_job_search", "zeal": "zeil"}
    return alias_map.get(value, value)


def parse_json_records(raw_text: str) -> list[dict]:
    value = json.loads(raw_text or "[]")
    return value if isinstance(value, list) else []


def metric_card(title: str, value: str, caption: str = "") -> None:
    st.markdown(
        f"""
        <div class="jb-card">
            <div class="jb-label">{title}</div>
            <div class="jb-value">{value}</div>
            <div class="jb-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(label: str, ok: bool) -> str:
    css_class = "jb-ok" if ok else "jb-warn"
    return f'<span class="jb-badge {css_class}">{label}</span>'


def empty_fill_metadata() -> dict:
    return {
        "filled_fields": [],
        "uploaded_files": [],
        "generated_answers": {},
        "skipped_fields": [],
        "verified_fields": [],
        "unresolved_required_fields": [],
        "unresolved_optional_fields": [],
        "rounds_completed": 0,
        "ready_to_advance": True,
    }


settings = config_manager.load_settings()
profile = config_manager.load_profile()
snapshot = st.session_state.run_snapshot or config_manager.latest_run_snapshot()
resume_path = settings.resume_path or config_manager.resolve_resume_path()
latest_logs = config_manager.latest_log_text()
latest_assets = config_manager.latest_generated_assets()
site_options = supported_site_names()

ollama_client = OllamaClient(settings.ollama)
ollama_ok, ollama_message = ollama_client.healthcheck()
attach_ok, attach_message, _ = probe_remote_browser(settings.browser.remote_debugging_url)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(221, 232, 255, 0.45), transparent 32%),
            radial-gradient(circle at top right, rgba(214, 240, 227, 0.40), transparent 28%),
            #f6f8fb;
    }
    .jb-hero {
        background: rgba(255, 255, 255, 0.78);
        border: 1px solid rgba(27, 34, 44, 0.08);
        border-radius: 22px;
        padding: 1.2rem 1.25rem 1.1rem 1.25rem;
        backdrop-filter: blur(8px);
        margin-bottom: 0.9rem;
    }
    .jb-title {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: #16202a;
    }
    .jb-subtitle {
        color: #5f6977;
        font-size: 0.96rem;
        margin-top: 0.25rem;
    }
    .jb-card {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(27, 34, 44, 0.08);
        border-radius: 18px;
        padding: 0.95rem 1rem;
        min-height: 118px;
    }
    .jb-label {
        color: #64707d;
        font-size: 0.84rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .jb-value {
        color: #17212b;
        font-size: 1.55rem;
        line-height: 1.15;
        font-weight: 700;
        margin-top: 0.2rem;
    }
    .jb-caption {
        color: #6a7481;
        font-size: 0.9rem;
        margin-top: 0.35rem;
        word-break: break-word;
    }
    .jb-badge {
        display: inline-block;
        padding: 0.3rem 0.55rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
    }
    .jb-ok {
        background: rgba(37, 161, 92, 0.13);
        color: #167443;
    }
    .jb-warn {
        background: rgba(210, 128, 34, 0.14);
        color: #91540a;
    }
    .jb-panel {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid rgba(27, 34, 44, 0.08);
        border-radius: 20px;
        padding: 1rem 1rem 0.35rem 1rem;
        margin-bottom: 0.9rem;
    }
    .jb-mini {
        color: #66717e;
        font-size: 0.88rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="jb-hero">
        <div class="jb-title">JobBot</div>
        <div class="jb-subtitle">
            Local job automation workspace with safer dry-run flow, browser attach support, and iterative form verification.
        </div>
        <div style="margin-top:0.75rem;">
            {status_badge("Profile Ready", bool(profile.full_name and profile.email))}
            {status_badge("Resume Ready", bool(resume_path))}
            {status_badge("Ollama Online", bool(ollama_ok or not settings.ollama.enabled))}
            {status_badge("Attach Ready", bool(attach_ok or not settings.browser.attach_to_existing_browser))}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

top1, top2, top3, top4 = st.columns(4)
with top1:
    metric_card("Run", str(snapshot.get("status", "idle")).replace("_", " ").title() if snapshot else "Idle", snapshot.get("stage", "Waiting").replace("_", " ").title() if snapshot else "Waiting")
with top2:
    metric_card("Progress", f"{int((snapshot.get('progress_ratio', 0.0) if snapshot else 0.0) * 100)}%", f"{snapshot.get('current_job_index', 0) if snapshot else 0} completed")
with top3:
    metric_card("Site", canonical_site(settings.run.site).replace("_", " ").title(), settings.run.query)
with top4:
    metric_card("Safety", "Dry Run" if settings.run.dry_run else "Live", "Stops before submit" if settings.run.stop_before_submit else "Submission allowed")

main_col, side_col = st.columns([1.55, 0.95])

with side_col:
    st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
    st.subheader("Quick Actions")
    start_clicked = st.button("Start Automation", type="primary", use_container_width=True)
    continue_clicked = st.button("Continue Checkpoint", use_container_width=True)
    stop_clicked = st.button("Stop Run", use_container_width=True)
    refresh_clicked = st.button("Refresh", use_container_width=True)

    st.divider()
    st.caption("Current browser")
    st.write(snapshot.get("current_title", "No active page") if snapshot else "No active page")
    st.caption(snapshot.get("current_url", "") if snapshot else "")

    st.divider()
    st.caption("Engine")
    st.write(settings.run.primary_engine)
    st.caption("Fallback")
    st.write(settings.run.fallback_engine)

    st.divider()
    st.caption("Services")
    st.write(f"Ollama: {'Online' if ollama_ok else 'Offline'}")
    st.caption(ollama_message)
    if settings.browser.attach_to_existing_browser:
        st.write(f"Attach: {'Ready' if attach_ok else 'Unavailable'}")
        st.caption(attach_message)
    st.markdown("</div>", unsafe_allow_html=True)

with main_col:
    tabs = st.tabs(["Command", "Setup", "Results"])

    with tabs[0]:
        command_left, command_right = st.columns([1.1, 0.9])
        with command_left:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Live Run")
            live_snapshot = st.session_state.run_snapshot or snapshot
            if live_snapshot:
                st.progress(float(live_snapshot.get("progress_ratio", 0.0)))
                checkpoint = live_snapshot.get("pending_checkpoint")
                if checkpoint:
                    st.warning(checkpoint.get("message", "Checkpoint waiting."))
                elif live_snapshot.get("status") == "completed":
                    st.success("Run completed.")
                elif live_snapshot.get("status") == "failed":
                    st.error(live_snapshot.get("last_error", "Run failed."))
                else:
                    st.info("Ready to run or resume.")

                st.json(
                    {
                        "status": live_snapshot.get("status"),
                        "stage": live_snapshot.get("stage"),
                        "site": live_snapshot.get("site"),
                        "query": live_snapshot.get("query"),
                        "location": live_snapshot.get("location"),
                        "engine": live_snapshot.get("engine"),
                    }
                )
            else:
                st.info("No run has been started yet.")
            st.markdown("</div>", unsafe_allow_html=True)

        with command_right:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Readiness")
            readiness = [
                ("Profile", bool(profile.full_name and profile.email)),
                ("Resume", bool(resume_path)),
                ("Ollama", bool(ollama_ok or not settings.ollama.enabled)),
                ("Attach", bool(attach_ok or not settings.browser.attach_to_existing_browser)),
            ]
            for label, ok in readiness:
                if ok:
                    st.success(f"{label} ready")
                else:
                    st.warning(f"{label} needs attention")
            st.caption("Supported sites")
            st.write(", ".join(site_options))
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
        st.subheader("Verification")
        latest_result = (snapshot.get("job_results", [])[-1] if snapshot and snapshot.get("job_results") else {}) if snapshot else {}
        verification = latest_result.get("metadata", empty_fill_metadata()) if latest_result else empty_fill_metadata()
        v1, v2, v3, v4 = st.columns(4)
        with v1:
            metric_card("Rounds", str(verification.get("rounds_completed", 0)), "Validation passes")
        with v2:
            metric_card("Verified", str(len(verification.get("verified_fields", []))), "Fields confirmed")
        with v3:
            metric_card("Required Gaps", str(len(verification.get("unresolved_required_fields", []))), "Still unresolved")
        with v4:
            metric_card("Optional Gaps", str(len(verification.get("unresolved_optional_fields", []))), "Could be reviewed")

        unresolved_required = verification.get("unresolved_required_fields", [])
        unresolved_optional = verification.get("unresolved_optional_fields", [])
        if unresolved_required:
            st.warning("Required fields still needing confirmation: " + ", ".join(unresolved_required[:10]))
        elif verification.get("verified_fields"):
            st.success("Latest form pass verified all required mapped fields before moving on.")
        else:
            st.info("Verification summary will appear after the first application flow.")
        if unresolved_optional:
            st.caption("Optional fields to review: " + ", ".join(unresolved_optional[:10]))
        st.markdown("</div>", unsafe_allow_html=True)

    with tabs[1]:
        setup_main, setup_side = st.columns([1.08, 0.92])
        with setup_main:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Run Setup")
            with st.form("run_setup_form"):
                col1, col2 = st.columns(2)
                site = col1.selectbox(
                    "Site",
                    options=site_options,
                    index=site_options.index(canonical_site(settings.run.site)) if canonical_site(settings.run.site) in site_options else 0,
                )
                query = col2.text_input("Keywords", value=settings.run.query)
                location = col1.text_input("Location", value=settings.run.location)
                start_url = col2.text_input("Start URL", value=settings.run.start_url)
                max_jobs = col1.number_input("Max jobs", min_value=1, max_value=30, value=settings.run.max_jobs)
                job_urls_text = col2.text_area("Direct job URLs", value="\n".join(settings.run.job_urls), height=120)
                dry_run = col1.checkbox("Dry run", value=settings.run.dry_run)
                stop_before_submit = col2.checkbox("Stop before submit", value=settings.run.stop_before_submit)
                stop_on_captcha = col1.checkbox("Stop on CAPTCHA", value=settings.run.stop_on_captcha)
                auto_fill_generic_forms = col2.checkbox("Iterative form verification", value=settings.run.auto_fill_generic_forms)
                auto_generate_cover_letter = col1.checkbox("Generate cover letters", value=settings.run.auto_generate_cover_letter)
                auto_answer_screening_questions = col2.checkbox("Answer screening questions", value=settings.run.auto_answer_screening_questions)
                save_run_clicked = st.form_submit_button("Save Run Setup")
            st.markdown("</div>", unsafe_allow_html=True)

            if save_run_clicked:
                new_settings = AppSettings.from_dict(settings.to_dict())
                new_settings.run.site = canonical_site(site)
                new_settings.run.query = query
                new_settings.run.location = location
                new_settings.run.start_url = start_url.strip()
                new_settings.run.max_jobs = int(max_jobs)
                new_settings.run.job_urls = [line.strip() for line in job_urls_text.splitlines() if line.strip()]
                new_settings.run.dry_run = dry_run
                new_settings.run.stop_before_submit = stop_before_submit
                new_settings.run.stop_on_captcha = stop_on_captcha
                new_settings.run.auto_fill_generic_forms = auto_fill_generic_forms
                new_settings.run.auto_generate_cover_letter = auto_generate_cover_letter
                new_settings.run.auto_answer_screening_questions = auto_answer_screening_questions
                config_manager.save_settings(new_settings)
                settings = new_settings
                st.success("Run setup saved.")

        with setup_side:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Browser + Resume")
            with st.form("runtime_settings_form"):
                b1, b2 = st.columns(2)
                attach_to_existing_browser = b1.checkbox("Attach to existing browser", value=settings.browser.attach_to_existing_browser)
                reuse_current_page_on_attach = b2.checkbox("Reuse current page", value=settings.browser.reuse_current_page_on_attach)
                keep_browser_open = b1.checkbox("Keep browser open", value=settings.browser.keep_browser_open)
                headless = b2.checkbox("Headless", value=settings.browser.headless)
                browser_binary_path = st.text_input("Brave/Chrome path", value=settings.browser.browser_binary_path)
                remote_debugging_url = st.text_input("Remote debugging URL", value=settings.browser.remote_debugging_url)
                browser_user_data_dir = st.text_input("Browser profile dir", value=settings.browser.browser_user_data_dir)
                timeout_ms = b1.number_input("Timeout (ms)", min_value=3000, value=settings.browser.timeout_ms, step=1000)
                slow_mo_ms = b2.number_input("Slow motion (ms)", min_value=0, value=settings.browser.slow_mo_ms, step=50)
                screenshot_on_failure = b1.checkbox("Screenshots on failure", value=settings.browser.screenshot_on_failure)
                resume_file = st.file_uploader("Resume PDF", type=["pdf"])
                resume_override = st.text_input("Resume path", value=resume_path)
                save_runtime_clicked = st.form_submit_button("Save Browser Settings")
            st.markdown("</div>", unsafe_allow_html=True)

            if save_runtime_clicked:
                new_settings = AppSettings.from_dict(settings.to_dict())
                new_settings.browser.attach_to_existing_browser = attach_to_existing_browser
                new_settings.browser.reuse_current_page_on_attach = reuse_current_page_on_attach
                new_settings.browser.keep_browser_open = keep_browser_open
                new_settings.browser.headless = headless
                new_settings.browser.browser_binary_path = browser_binary_path
                new_settings.browser.remote_debugging_url = remote_debugging_url
                new_settings.browser.browser_user_data_dir = browser_user_data_dir
                new_settings.browser.timeout_ms = int(timeout_ms)
                new_settings.browser.slow_mo_ms = int(slow_mo_ms)
                new_settings.browser.screenshot_on_failure = screenshot_on_failure
                new_settings.resume_path = resume_override
                if resume_file is not None:
                    new_settings.resume_path = config_manager.save_resume_bytes(resume_file.name, resume_file.getvalue())
                config_manager.save_settings(new_settings)
                settings = new_settings
                st.success("Browser settings saved.")

            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Profile")
            with st.form("profile_form"):
                p1, p2 = st.columns(2)
                full_name = p1.text_input("Name", value=profile.full_name)
                email = p2.text_input("Email", value=profile.email)
                phone = p1.text_input("Phone", value=profile.phone)
                location_profile = p2.text_input("Location", value=profile.location)
                linkedin_url = p1.text_input("LinkedIn", value=profile.linkedin_url)
                portfolio_url = p2.text_input("Portfolio", value=profile.portfolio_url)
                summary = st.text_area("Summary", value=profile.summary, height=120)
                skills_text = st.text_area("Skills", value="\n".join(profile.skills), height=100)
                custom_answers_text = st.text_area("Custom answers JSON", value=json.dumps(profile.custom_answers, indent=2), height=140)
                employment_text = st.text_area("Employment JSON", value=json.dumps([record.__dict__ for record in profile.employment], indent=2), height=130)
                education_text = st.text_area("Education JSON", value=json.dumps([record.__dict__ for record in profile.education], indent=2), height=120)
                work_authorization = p1.text_input("Work authorization", value=profile.work_authorization)
                remote_preference = p2.text_input("Remote preference", value=profile.remote_preference)
                salary_expectation = p1.text_input("Salary expectation", value=profile.salary_expectation)
                notice_period = p2.text_input("Availability", value=profile.notice_period)
                save_profile_clicked = st.form_submit_button("Save Profile")
            st.markdown("</div>", unsafe_allow_html=True)

            if save_profile_clicked:
                try:
                    new_profile = ProfileData(
                        full_name=full_name,
                        email=email,
                        phone=phone,
                        location=location_profile,
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
                    profile = new_profile
                    st.success("Profile saved.")
                except json.JSONDecodeError as exc:
                    st.error(f"Could not parse the JSON blocks: {exc}")

    with tabs[2]:
        results_top, results_bottom = st.columns([1.05, 0.95])
        with results_top:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Recent Results")
            if snapshot and snapshot.get("job_results"):
                st.dataframe(snapshot.get("job_results"), use_container_width=True)
            else:
                st.info("No job results yet.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Logs")
            if latest_logs:
                st.code("\n".join(latest_logs.splitlines()[-60:]), language="text")
            else:
                st.info("No logs yet.")
            st.markdown("</div>", unsafe_allow_html=True)

        with results_bottom:
            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Generated Content")
            if latest_assets:
                selected_asset = st.selectbox("Artifact", options=list(latest_assets.keys()))
                st.code(latest_assets[selected_asset], language="markdown")
            else:
                st.info("No generated content yet.")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="jb-panel">', unsafe_allow_html=True)
            st.subheader("Snapshot")
            if snapshot:
                st.json(
                    {
                        "status": snapshot.get("status"),
                        "stage": snapshot.get("stage"),
                        "engine": snapshot.get("engine"),
                        "site": snapshot.get("site"),
                        "current_url": snapshot.get("current_url"),
                        "log_path": snapshot.get("log_path"),
                    }
                )
            else:
                st.info("No snapshot yet.")
            st.markdown("</div>", unsafe_allow_html=True)


if start_clicked:
    controller = AutomationController(config_manager)
    st.session_state.controller = controller
    st.session_state.run_snapshot = controller.start(
        {
            "run": {
                "site": settings.run.site,
                "query": settings.run.query,
                "location": settings.run.location,
                "start_url": settings.run.start_url,
                "job_urls": settings.run.job_urls,
                "primary_engine": settings.run.primary_engine,
                "fallback_engine": settings.run.fallback_engine,
                "max_jobs": settings.run.max_jobs,
                "dry_run": settings.run.dry_run,
                "stop_before_submit": settings.run.stop_before_submit,
                "stop_on_captcha": settings.run.stop_on_captcha,
                "auto_generate_cover_letter": settings.run.auto_generate_cover_letter,
                "auto_answer_screening_questions": settings.run.auto_answer_screening_questions,
                "auto_fill_generic_forms": settings.run.auto_fill_generic_forms,
            },
            "browser": {
                "attach_to_existing_browser": settings.browser.attach_to_existing_browser,
                "remote_debugging_url": settings.browser.remote_debugging_url,
                "reuse_current_page_on_attach": settings.browser.reuse_current_page_on_attach,
                "keep_browser_open": settings.browser.keep_browser_open,
            },
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

if refresh_clicked:
    st.session_state.run_snapshot = config_manager.latest_run_snapshot()
    st.rerun()
