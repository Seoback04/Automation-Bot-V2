from __future__ import annotations

from dataclasses import dataclass

from jobbot.ai.ollama_client import OllamaClient
from jobbot.automation.engines.base import BrowserEngine
from jobbot.config.models import ProfileData, RunSettings
from jobbot.utils.run_logger import RunLogger


@dataclass
class FillResult:
    filled_fields: list[str]
    uploaded_files: list[str]
    generated_answers: dict[str, str]
    skipped_fields: list[str]

    def to_dict(self) -> dict:
        return {
            "filled_fields": self.filled_fields,
            "uploaded_files": self.uploaded_files,
            "generated_answers": self.generated_answers,
            "skipped_fields": self.skipped_fields,
        }


class GenericFormFiller:
    def __init__(self, engine: BrowserEngine, logger: RunLogger) -> None:
        self.engine = engine
        self.logger = logger

    def fill_application_form(
        self,
        profile: ProfileData,
        job: dict,
        run_settings: RunSettings,
        ai_client: OllamaClient,
        resume_path: str,
        cover_letter: str,
    ) -> FillResult:
        latest_employment = profile.employment[0] if profile.employment else None
        latest_education = profile.education[0] if profile.education else None
        fields = self.engine.scan_form_fields()

        filled_fields: list[str] = []
        uploaded_files: list[str] = []
        generated_answers: dict[str, str] = {}
        skipped_fields: list[str] = []

        for field in fields:
            if not field.get("visible") or field.get("disabled"):
                continue

            descriptor = self._descriptor_text(field)
            field_type = (field.get("type") or "").lower()
            tag = (field.get("tag") or "").lower()

            if field_type in {"hidden", "submit", "button", "search", "password"}:
                continue

            if field_type == "file":
                if resume_path:
                    try:
                        self.engine.upload_file_by_index(int(field["index"]), resume_path)
                        uploaded_files.append(descriptor or f"file_{field['index']}")
                    except Exception as exc:  # noqa: BLE001
                        self.logger.warning("Generic resume upload failed.", field=descriptor, error=repr(exc))
                continue

            if field_type in {"checkbox", "radio"}:
                skipped_fields.append(descriptor or f"choice_{field['index']}")
                continue

            value = self._resolve_value(
                descriptor=descriptor,
                field=field,
                profile=profile,
                latest_employment=latest_employment,
                latest_education=latest_education,
                cover_letter=cover_letter,
            )

            if not value and run_settings.auto_answer_screening_questions and self._looks_like_question(descriptor):
                value = ai_client.answer_application_question(descriptor, job, profile)
                if value:
                    generated_answers[descriptor] = value

            if not value:
                skipped_fields.append(descriptor or f"field_{field['index']}")
                continue

            try:
                if tag == "select":
                    option = self._pick_option(field.get("options", []), value)
                    if option:
                        self.engine.select_option_by_index(int(field["index"]), option)
                        filled_fields.append(descriptor)
                    else:
                        skipped_fields.append(descriptor)
                else:
                    self.engine.fill_field_by_index(int(field["index"]), value)
                    filled_fields.append(descriptor)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Generic field fill failed.", field=descriptor, error=repr(exc))
                skipped_fields.append(descriptor or f"field_{field['index']}")

        return FillResult(
            filled_fields=filled_fields,
            uploaded_files=uploaded_files,
            generated_answers=generated_answers,
            skipped_fields=skipped_fields,
        )

    def _descriptor_text(self, field: dict) -> str:
        parts = [
            str(field.get("label", "")),
            str(field.get("aria_label", "")),
            str(field.get("placeholder", "")),
            str(field.get("name", "")),
            str(field.get("id", "")),
            str(field.get("autocomplete", "")),
            str(field.get("title", "")),
        ]
        return " ".join(part.strip() for part in parts if part and part.strip()).strip().lower()

    def _resolve_value(
        self,
        descriptor: str,
        field: dict,
        profile: ProfileData,
        latest_employment,
        latest_education,
        cover_letter: str,
    ) -> str:
        full_name = profile.full_name.strip()
        parts = full_name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        mapping = [
            (("first name", "given name"), first_name),
            (("last name", "surname", "family name"), last_name),
            (("full name", "your name", "applicant name"), full_name),
            (("email", "e-mail"), profile.email),
            (("phone", "mobile", "contact number", "telephone"), profile.phone),
            (("linkedin",), profile.linkedin_url),
            (("portfolio", "website", "personal site"), profile.portfolio_url),
            (("city", "location", "suburb", "address"), profile.location),
            (("salary", "pay expectation", "compensation"), profile.salary_expectation),
            (("notice period", "availability", "start date"), profile.notice_period),
            (("work authorization", "authorised", "authorized", "visa", "sponsorship"), profile.work_authorization),
            (("remote", "work preference"), profile.remote_preference),
            (("cover letter",), cover_letter),
            (("summary", "about you", "background", "profile", "bio"), profile.summary),
            (("skills", "technologies", "expertise"), ", ".join(profile.skills)),
            (("current company", "employer", "company"), latest_employment.company if latest_employment else ""),
            (("job title", "current title", "position title"), latest_employment.title if latest_employment else ""),
            (("school", "university", "institution"), latest_education.school if latest_education else ""),
            (("degree",), latest_education.degree if latest_education else ""),
            (("field of study", "major"), latest_education.field_of_study if latest_education else ""),
        ]

        for keywords, value in mapping:
            if value and any(keyword in descriptor for keyword in keywords):
                return value

        for keyword, answer in profile.custom_answers.items():
            if answer and keyword.lower() in descriptor:
                return answer

        if "why" in descriptor or "motivation" in descriptor:
            return cover_letter or profile.summary

        if field.get("tag") == "select":
            options = [str(option).strip() for option in field.get("options", []) if str(option).strip()]
            yes_no = self._pick_yes_no_option(descriptor, options, profile)
            if yes_no:
                return yes_no

        return ""

    def _pick_option(self, options: list[str], desired_value: str) -> str:
        desired = desired_value.strip().lower()
        exact = next((option for option in options if option.strip().lower() == desired), "")
        if exact:
            return exact

        partial = next((option for option in options if desired and desired in option.strip().lower()), "")
        if partial:
            return partial

        reverse = next((option for option in options if option.strip().lower() in desired), "")
        return reverse

    def _pick_yes_no_option(self, descriptor: str, options: list[str], profile: ProfileData) -> str:
        if not options:
            return ""
        normalized = [option.strip().lower() for option in options]
        if any(keyword in descriptor for keyword in ("authorized", "authorised", "visa", "work rights")):
            if "yes" in normalized:
                return options[normalized.index("yes")]
        if "remote" in descriptor and profile.remote_preference:
            return self._pick_option(options, profile.remote_preference)
        return ""

    def _looks_like_question(self, descriptor: str) -> bool:
        return len(descriptor) > 12 and any(token in descriptor for token in ("why", "describe", "tell us", "experience", "?"))
