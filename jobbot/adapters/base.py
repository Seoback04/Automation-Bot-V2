from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.engines.base import BrowserEngine
from jobbot.config.models import ProfileData, RunSettings
from jobbot.utils.run_logger import RunLogger


@dataclass
class JobPosting:
    site: str
    url: str
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "url": self.url,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "metadata": self.metadata,
        }


@dataclass
class PreparedApplication:
    status: str
    notes: str = ""
    submit_selectors: list[str] = field(default_factory=list)
    generated_cover_letter: str = ""
    generated_answers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class JobSiteAdapter:
    site_name = "base"

    def __init__(self, engine: BrowserEngine, logger: RunLogger) -> None:
        self.engine = engine
        self.logger = logger

    def open_search_page(self, query: str, location: str) -> None:
        raise NotImplementedError

    def collect_job_links(self, max_jobs: int) -> list[str]:
        raise NotImplementedError

    def open_job(self, url: str) -> None:
        self.engine.goto(url)
        self.engine.sleep(1.5)

    def extract_job(self, url: str) -> JobPosting:
        raise NotImplementedError

    def detect_captcha(self) -> bool:
        return self.engine.exists_any(
            [
                "iframe[title*='challenge']",
                "iframe[src*='captcha']",
                "xpath=//*[contains(translate(normalize-space(.), 'CAPTCHA', 'captcha'), 'captcha')]",
                "xpath=//*[contains(translate(normalize-space(.), 'VERIFY', 'verify'), 'verify you are human')]",
            ]
        )

    def prepare_application(
        self,
        job: JobPosting,
        profile: ProfileData,
        run_settings: RunSettings,
        resume_path: str,
        ai_client: OllamaClient,
        cover_letter: str = "",
    ) -> PreparedApplication:
        raise NotImplementedError

    def submit_application(self, submit_selectors: list[str]) -> str:
        self.engine.click_any(submit_selectors)
        return "Submitted via site adapter."

    def close_application_dialog(self) -> None:
        self.engine.try_click_any(
            [
                "button[aria-label*='Dismiss']",
                "button[aria-label*='Close']",
                "button[aria-label*='Discard']",
                "xpath=//button[contains(normalize-space(.), 'Close')]",
                "xpath=//button[contains(normalize-space(.), 'Dismiss')]",
            ]
        )
