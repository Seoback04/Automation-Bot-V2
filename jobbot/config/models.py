from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EducationRecord:
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: str = ""
    end_date: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EducationRecord":
        return cls(
            school=payload.get("school", ""),
            degree=payload.get("degree", ""),
            field_of_study=payload.get("field_of_study", ""),
            start_date=payload.get("start_date", ""),
            end_date=payload.get("end_date", ""),
        )


@dataclass
class EmploymentRecord:
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    achievements: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EmploymentRecord":
        return cls(
            company=payload.get("company", ""),
            title=payload.get("title", ""),
            start_date=payload.get("start_date", ""),
            end_date=payload.get("end_date", ""),
            achievements=list(payload.get("achievements", [])),
        )


@dataclass
class ProfileData:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    work_authorization: str = ""
    salary_expectation: str = ""
    remote_preference: str = ""
    notice_period: str = ""
    custom_answers: dict[str, str] = field(default_factory=dict)
    education: list[EducationRecord] = field(default_factory=list)
    employment: list[EmploymentRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProfileData":
        return cls(
            full_name=payload.get("full_name", ""),
            email=payload.get("email", ""),
            phone=payload.get("phone", ""),
            location=payload.get("location", ""),
            linkedin_url=payload.get("linkedin_url", ""),
            portfolio_url=payload.get("portfolio_url", ""),
            summary=payload.get("summary", ""),
            skills=list(payload.get("skills", [])),
            work_authorization=payload.get("work_authorization", ""),
            salary_expectation=payload.get("salary_expectation", ""),
            remote_preference=payload.get("remote_preference", ""),
            notice_period=payload.get("notice_period", ""),
            custom_answers=dict(payload.get("custom_answers", {})),
            education=[
                EducationRecord.from_dict(item)
                for item in payload.get("education", [])
                if isinstance(item, dict)
            ],
            employment=[
                EmploymentRecord.from_dict(item)
                for item in payload.get("employment", [])
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserSettings:
    browser_binary_path: str = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    browser_user_data_dir: str = ""
    headless: bool = False
    slow_mo_ms: int = 150
    timeout_ms: int = 15000
    screenshot_on_failure: bool = True
    attach_to_existing_browser: bool = False
    remote_debugging_url: str = "http://127.0.0.1:9222"
    reuse_current_page_on_attach: bool = True
    keep_browser_open: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrowserSettings":
        return cls(
            browser_binary_path=payload.get("browser_binary_path", cls.browser_binary_path),
            browser_user_data_dir=payload.get("browser_user_data_dir", ""),
            headless=bool(payload.get("headless", False)),
            slow_mo_ms=int(payload.get("slow_mo_ms", 150)),
            timeout_ms=int(payload.get("timeout_ms", 15000)),
            screenshot_on_failure=bool(payload.get("screenshot_on_failure", True)),
            attach_to_existing_browser=bool(payload.get("attach_to_existing_browser", False)),
            remote_debugging_url=payload.get("remote_debugging_url", "http://127.0.0.1:9222"),
            reuse_current_page_on_attach=bool(payload.get("reuse_current_page_on_attach", True)),
            keep_browser_open=bool(payload.get("keep_browser_open", True)),
        )


@dataclass
class OllamaSettings:
    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.1:8b"
    request_timeout_seconds: int = 90
    temperature: float = 0.2

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OllamaSettings":
        return cls(
            enabled=bool(payload.get("enabled", True)),
            base_url=payload.get("base_url", "http://127.0.0.1:11434"),
            model=payload.get("model", "llama3.1:8b"),
            request_timeout_seconds=int(payload.get("request_timeout_seconds", 90)),
            temperature=float(payload.get("temperature", 0.2)),
        )


@dataclass
class RunSettings:
    primary_engine: str = "playwright"
    fallback_engine: str = "selenium"
    site: str = "linkedin"
    query: str = "Software Engineer"
    location: str = "Auckland"
    start_url: str = ""
    job_urls: list[str] = field(default_factory=list)
    max_jobs: int = 3
    dry_run: bool = True
    stop_on_captcha: bool = True
    stop_before_submit: bool = True
    take_screenshots: bool = True
    auto_generate_cover_letter: bool = True
    auto_answer_screening_questions: bool = True
    auto_fill_generic_forms: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunSettings":
        return cls(
            primary_engine=payload.get("primary_engine", "playwright"),
            fallback_engine=payload.get("fallback_engine", "selenium"),
            site=payload.get("site", "linkedin"),
            query=payload.get("query", "Software Engineer"),
            location=payload.get("location", "Auckland"),
            start_url=payload.get("start_url", ""),
            job_urls=[item for item in payload.get("job_urls", []) if isinstance(item, str) and item.strip()],
            max_jobs=int(payload.get("max_jobs", 3)),
            dry_run=bool(payload.get("dry_run", True)),
            stop_on_captcha=bool(payload.get("stop_on_captcha", True)),
            stop_before_submit=bool(payload.get("stop_before_submit", True)),
            take_screenshots=bool(payload.get("take_screenshots", True)),
            auto_generate_cover_letter=bool(payload.get("auto_generate_cover_letter", True)),
            auto_answer_screening_questions=bool(payload.get("auto_answer_screening_questions", True)),
            auto_fill_generic_forms=bool(payload.get("auto_fill_generic_forms", True)),
        )


@dataclass
class AppSettings:
    resume_path: str = ""
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    run: RunSettings = field(default_factory=RunSettings)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppSettings":
        return cls(
            resume_path=payload.get("resume_path", ""),
            browser=BrowserSettings.from_dict(payload.get("browser", {})),
            ollama=OllamaSettings.from_dict(payload.get("ollama", {})),
            run=RunSettings.from_dict(payload.get("run", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
