from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jobbot.config.models import AppSettings, EmploymentRecord, ProfileData
from jobbot.utils.paths import (
    DATA_DIR,
    BROWSER_PROFILE_DIR,
    CONFIG_DIR,
    RESUMES_DIR,
    RUNS_DIR,
    ensure_data_directories,
)


class ConfigManager:
    def __init__(self) -> None:
        ensure_data_directories()
        self.profile_path = CONFIG_DIR / "profile.json"
        self.settings_path = CONFIG_DIR / "settings.json"
        self.ensure_defaults()

    def ensure_defaults(self) -> None:
        if not self.profile_path.exists():
            default_profile = ProfileData(
                full_name="Your Name",
                email="your.email@example.com",
                phone="+64 21 000 0000",
                location="Auckland, New Zealand",
                linkedin_url="https://www.linkedin.com/in/your-profile",
                summary="Local automation-ready profile used to prefill job applications.",
                skills=["Python", "Automation", "Testing", "Playwright"],
                work_authorization="Open to work in New Zealand",
                remote_preference="Hybrid",
                notice_period="2 weeks",
                custom_answers={
                    "visa": "I am eligible to work in New Zealand.",
                    "salary": "Happy to discuss based on the role scope and package.",
                },
                employment=[
                    EmploymentRecord(
                        company="Example Co",
                        title="QA Automation Engineer",
                        start_date="2024-01",
                        end_date="Present",
                        achievements=[
                            "Built browser automation for regression coverage.",
                            "Improved release confidence with repeatable test workflows.",
                        ],
                    )
                ],
            )
            self.save_profile(default_profile)

        if not self.settings_path.exists():
            default_settings = AppSettings()
            default_settings.browser.browser_user_data_dir = str(BROWSER_PROFILE_DIR)
            self.save_settings(default_settings)

    def load_profile(self) -> ProfileData:
        return ProfileData.from_dict(self._read_json(self.profile_path, {}))

    def save_profile(self, profile: ProfileData) -> None:
        self._write_json(self.profile_path, profile.to_dict())

    def load_settings(self) -> AppSettings:
        settings = AppSettings.from_dict(self._read_json(self.settings_path, {}))
        if not settings.browser.browser_user_data_dir:
            settings.browser.browser_user_data_dir = str(BROWSER_PROFILE_DIR)
        return settings

    def save_settings(self, settings: AppSettings) -> None:
        if not settings.browser.browser_user_data_dir:
            settings.browser.browser_user_data_dir = str(BROWSER_PROFILE_DIR)
        self._write_json(self.settings_path, settings.to_dict())

    def save_resume_bytes(self, file_name: str, content: bytes) -> str:
        safe_name = Path(file_name).name or "resume.pdf"
        destination = RESUMES_DIR / safe_name
        destination.write_bytes(content)

        settings = self.load_settings()
        settings.resume_path = str(destination)
        self.save_settings(settings)
        return str(destination)

    def resolve_resume_path(self) -> str:
        settings = self.load_settings()
        if settings.resume_path and Path(settings.resume_path).exists():
            return settings.resume_path

        candidates = sorted(RESUMES_DIR.glob("*.pdf"))
        if not candidates:
            candidates = sorted(DATA_DIR.glob("*.pdf"))
        if candidates:
            return str(candidates[-1])
        return ""

    def latest_run_dir(self) -> Path | None:
        candidates = sorted([path for path in RUNS_DIR.iterdir() if path.is_dir()], reverse=True)
        return candidates[0] if candidates else None

    def latest_run_snapshot(self) -> dict[str, Any]:
        latest = self.latest_run_dir()
        if not latest:
            return {}
        snapshot_path = latest / "run_snapshot.json"
        if not snapshot_path.exists():
            return {}
        return self._read_json(snapshot_path, {})

    def latest_log_text(self) -> str:
        latest = self.latest_run_dir()
        if not latest:
            return ""
        log_path = latest / "app.log"
        return log_path.read_text(encoding="utf-8") if log_path.exists() else ""

    def latest_generated_assets(self) -> dict[str, str]:
        latest = self.latest_run_dir()
        assets: dict[str, str] = {}
        if not latest:
            return assets
        generated_dir = latest / "generated"
        if not generated_dir.exists():
            return assets
        for path in sorted(generated_dir.glob("*.md")):
            assets[path.name] = path.read_text(encoding="utf-8")
        return assets

    def _read_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return fallback

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
