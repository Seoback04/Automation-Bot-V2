from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from jobbot.adapters.registry import create_adapter, supported_site_names
from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.engines.playwright_engine import PlaywrightEngine
from jobbot.automation.engines.selenium_engine import SeleniumEngine
from jobbot.config.manager import ConfigManager
from jobbot.config.models import AppSettings, ProfileData
from jobbot.utils.run_logger import RunLogger


class AutomationController:
    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        self.config_manager = config_manager or ConfigManager()
        self.profile: ProfileData | None = None
        self.settings: AppSettings | None = None
        self.active_run_settings: dict[str, Any] = {}
        self.logger: RunLogger | None = None
        self.ai_client: OllamaClient | None = None
        self.engine = None
        self.adapter = None
        self.state: dict[str, Any] = {}
        self.current_prepared_application: dict[str, Any] | None = None

    def start(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        self.profile = self.config_manager.load_profile()
        base_settings = self.config_manager.load_settings()
        base_settings.resume_path = self.config_manager.resolve_resume_path()
        self.active_run_settings = self._merge_run_settings(base_settings.to_dict(), overrides or {})
        self.settings = AppSettings.from_dict(self.active_run_settings)

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = RunLogger(run_id)
        self.ai_client = OllamaClient(self.settings.ollama)
        self.state = {
            "run_id": run_id,
            "status": "initializing",
            "stage": "booting",
            "engine": "",
            "site": self.active_run_settings["run"]["site"],
            "query": self.active_run_settings["run"]["query"],
            "location": self.active_run_settings["run"]["location"],
            "dry_run": self.active_run_settings["run"]["dry_run"],
            "resume_path": self.settings.resume_path,
            "job_links": [],
            "current_job_index": 0,
            "job_results": [],
            "generated_assets": {},
            "supported_sites": supported_site_names(),
            "pending_checkpoint": None,
            "last_error": "",
            "current_url": "",
            "current_title": "",
        }
        self.logger.info("Starting automation run.", site=self.state["site"], query=self.state["query"])

        self._start_engine()
        self.adapter = create_adapter(self.state["site"], self.engine, self.logger)
        self._open_run_entrypoint()
        self._refresh_browser_context()

        self.state["status"] = "checkpoint"
        self.state["stage"] = "awaiting_login"
        self.state["pending_checkpoint"] = {
            "kind": "manual_login",
            "message": (
                "Log in or position the attached browser on the desired jobs page. "
                "Complete MFA or any anti-bot checks, then return to Streamlit and continue."
            ),
        }
        return self.snapshot()

    def resume(self) -> dict[str, Any]:
        checkpoint = self.state.get("pending_checkpoint")
        if not checkpoint:
            return self.snapshot()

        kind = checkpoint.get("kind", "")
        self.state["pending_checkpoint"] = None

        if kind == "manual_login":
            self.state["stage"] = "collecting_jobs"
            self._refresh_browser_context()
            self.state["job_links"] = self._resolve_job_links()
            self.logger.info("Collected job links.", count=len(self.state["job_links"]))
            if not self.state["job_links"]:
                self.state["status"] = "completed"
                self.state["stage"] = "no_jobs_found"
                self._cleanup()
                return self.snapshot()
            return self._process_jobs()

        if kind == "captcha":
            self.logger.info("Captcha checkpoint cleared by user.")
            return self._process_jobs()

        if kind == "final_review":
            return self._handle_final_review_checkpoint()

        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        self.state["status"] = "stopped"
        self.state["stage"] = "stopped"
        if self.logger is not None:
            self.logger.info("Run stopped by user.")
        self._cleanup()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        snapshot = deepcopy(self.state)
        total = len(snapshot.get("job_links", []))
        current = snapshot.get("current_job_index", 0)
        snapshot["progress_ratio"] = round((current / total), 3) if total else 0.0
        if self.logger is not None:
            snapshot["run_dir"] = str(self.logger.run_dir)
            snapshot["log_path"] = str(self.logger.log_file)
            self.logger.save_snapshot(snapshot)
        return snapshot

    def _process_jobs(self) -> dict[str, Any]:
        try:
            while self.state["current_job_index"] < len(self.state["job_links"]):
                job_url = self.state["job_links"][self.state["current_job_index"]]
                self.logger.info("Opening job.", url=job_url, index=self.state["current_job_index"])
                self.adapter.open_job(job_url)
                self._refresh_browser_context()

                if self.adapter.detect_captcha() and self.active_run_settings["run"]["stop_on_captcha"]:
                    self.state["status"] = "checkpoint"
                    self.state["stage"] = "awaiting_captcha"
                    self.state["pending_checkpoint"] = {
                        "kind": "captcha",
                        "message": "A CAPTCHA or bot challenge was detected. Solve it in the browser, then continue.",
                    }
                    return self.snapshot()

                job = self.adapter.extract_job(job_url)
                analysis = self.ai_client.analyze_job_description(job.to_dict(), self.profile)
                cover_letter = (
                    self.ai_client.generate_cover_letter(job.to_dict(), self.profile)
                    if self.active_run_settings["run"]["auto_generate_cover_letter"]
                    else ""
                )

                asset_prefix = f"{self.state['current_job_index'] + 1:02d}_{job.site}_{job.company or 'company'}_{job.title or 'job'}"
                self.state["generated_assets"][f"{asset_prefix}_analysis.md"] = analysis
                self.logger.save_markdown(f"{asset_prefix}_analysis", analysis)
                if cover_letter:
                    self.state["generated_assets"][f"{asset_prefix}_cover_letter.md"] = cover_letter
                    self.logger.save_markdown(f"{asset_prefix}_cover_letter", cover_letter)

                prepared = self.adapter.prepare_application(
                    job=job,
                    profile=self.profile,
                    run_settings=self.settings.run,
                    resume_path=self.settings.resume_path,
                    ai_client=self.ai_client,
                )

                result = {
                    "url": job.url,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "status": prepared.status,
                    "notes": prepared.notes,
                    "analysis": analysis,
                    "cover_letter": cover_letter or prepared.generated_cover_letter,
                    "generated_answers": prepared.generated_answers,
                    "metadata": prepared.metadata,
                }

                if prepared.status == "review_ready":
                    self.current_prepared_application = {
                        "job_result": result,
                        "submit_selectors": prepared.submit_selectors,
                    }
                    self.state["status"] = "checkpoint"
                    self.state["stage"] = "awaiting_final_review"
                    self.state["pending_checkpoint"] = {
                        "kind": "final_review",
                        "message": (
                            "Review the prepared application in the browser. "
                            "If dry-run is enabled, do not submit it manually. "
                            "When you are ready, return here and continue."
                        ),
                    }
                    return self.snapshot()

                self.state["job_results"].append(result)
                self.state["current_job_index"] += 1

            self.state["status"] = "completed"
            self.state["stage"] = "finished"
            self.logger.info("Run completed.", processed_jobs=len(self.state["job_results"]))
            self._cleanup()
            return self.snapshot()
        except Exception as exc:  # noqa: BLE001
            self.state["status"] = "failed"
            self.state["stage"] = "failed"
            self.state["last_error"] = repr(exc)
            self.logger.exception("Run failed.", exc)
            if self.settings and self.settings.browser.screenshot_on_failure and self.engine is not None:
                screenshot_path = self.logger.screenshot_path("failure")
                try:
                    self.engine.screenshot(screenshot_path)
                    self.state["failure_screenshot"] = str(screenshot_path)
                except Exception:  # noqa: BLE001
                    pass
            self._cleanup()
            return self.snapshot()

    def _handle_final_review_checkpoint(self) -> dict[str, Any]:
        if not self.current_prepared_application:
            return self._process_jobs()

        job_result = self.current_prepared_application["job_result"]
        submit_selectors = self.current_prepared_application["submit_selectors"]

        if self.active_run_settings["run"]["dry_run"] or self.active_run_settings["run"]["stop_before_submit"]:
            job_result["status"] = "dry_run_reviewed"
            job_result["notes"] = (
                "Automation stopped before submission. Close or discard the site modal manually, then continue."
            )
            self.adapter.close_application_dialog()
            self.logger.info("Dry-run checkpoint cleared without submission.", url=job_result["url"])
        else:
            submission_note = self.adapter.submit_application(submit_selectors)
            job_result["status"] = "submitted"
            job_result["notes"] = submission_note
            self.logger.info("Application submitted.", url=job_result["url"])

        self.state["job_results"].append(job_result)
        self.state["current_job_index"] += 1
        self.current_prepared_application = None
        self.state["pending_checkpoint"] = None
        self.state["status"] = "running"
        self.state["stage"] = "processing_jobs"
        return self._process_jobs()

    def _start_engine(self) -> None:
        primary = self.active_run_settings["run"]["primary_engine"]
        fallback = self.active_run_settings["run"]["fallback_engine"]

        for engine_name in [primary, fallback]:
            try:
                self.engine = self._build_engine(engine_name)
                self.engine.start()
                self.state["engine"] = engine_name
                self.logger.info("Browser engine started.", engine=engine_name)
                return
            except Exception as exc:  # noqa: BLE001
                self.logger.exception(f"Failed to start browser engine {engine_name}.", exc)
                self.engine = None

        raise RuntimeError("Unable to start either the primary or fallback automation engine.")

    def _build_engine(self, engine_name: str):
        if engine_name == "playwright":
            return PlaywrightEngine(self.settings.browser, self.logger)
        if engine_name == "selenium":
            return SeleniumEngine(self.settings.browser, self.logger)
        raise ValueError(f"Unsupported engine: {engine_name}")

    def _merge_run_settings(self, settings_payload: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(settings_payload)
        run_overrides = overrides.get("run", {})
        browser_overrides = overrides.get("browser", {})
        merged["run"].update({key: value for key, value in run_overrides.items() if value is not None})
        merged["browser"].update({key: value for key, value in browser_overrides.items() if value is not None})
        return merged

    def _cleanup(self) -> None:
        if self.engine is not None:
            try:
                self.engine.close()
            except Exception:  # noqa: BLE001
                pass
            self.engine = None

    def _open_run_entrypoint(self) -> None:
        start_url = self.active_run_settings["run"].get("start_url", "").strip()
        attach_mode = self.settings.browser.attach_to_existing_browser and self.settings.browser.reuse_current_page_on_attach
        current_url = self.engine.current_url() if self.engine is not None else ""

        if start_url:
            self.engine.goto(start_url)
            self.logger.info("Opened explicit start URL.", url=start_url)
            return

        if attach_mode and current_url and current_url not in {"about:blank", "chrome://newtab/"}:
            self.logger.info("Reusing current attached browser tab.", url=current_url)
            return

        self.adapter.open_search_page(self.state["query"], self.state["location"])

    def _resolve_job_links(self) -> list[str]:
        direct_urls = [
            item.strip()
            for item in self.active_run_settings["run"].get("job_urls", [])
            if isinstance(item, str) and item.strip()
        ]
        if direct_urls:
            return direct_urls[: self.active_run_settings["run"]["max_jobs"]]

        try:
            job_links = self.adapter.collect_job_links(self.active_run_settings["run"]["max_jobs"])
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Job link collection failed.", exc)
            job_links = []

        current_url = self.engine.current_url()
        if not job_links and current_url and current_url not in {"about:blank", "chrome://newtab/"}:
            job_links = [current_url]
        return job_links

    def _refresh_browser_context(self) -> None:
        if self.engine is None:
            return
        try:
            self.state["current_url"] = self.engine.current_url()
        except Exception:  # noqa: BLE001
            self.state["current_url"] = ""
        try:
            self.state["current_title"] = self.engine.current_title()
        except Exception:  # noqa: BLE001
            self.state["current_title"] = ""
