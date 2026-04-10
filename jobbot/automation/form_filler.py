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
    verified_fields: list[str]
    unresolved_required_fields: list[str]
    unresolved_optional_fields: list[str]
    rounds_completed: int
    ready_to_advance: bool

    def to_dict(self) -> dict:
        return {
            "filled_fields": self.filled_fields,
            "uploaded_files": self.uploaded_files,
            "generated_answers": self.generated_answers,
            "skipped_fields": self.skipped_fields,
            "verified_fields": self.verified_fields,
            "unresolved_required_fields": self.unresolved_required_fields,
            "unresolved_optional_fields": self.unresolved_optional_fields,
            "rounds_completed": self.rounds_completed,
            "ready_to_advance": self.ready_to_advance,
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
        max_rounds: int = 3,
    ) -> FillResult:
        latest_employment = profile.employment[0] if profile.employment else None
        latest_education = profile.education[0] if profile.education else None

        filled_fields: list[str] = []
        uploaded_files: list[str] = []
        generated_answers: dict[str, str] = {}
        skipped_fields: list[str] = []
        verified_fields: list[str] = []
        unresolved_required_fields: list[str] = []
        unresolved_optional_fields: list[str] = []
        field_expectations: dict[int, dict] = {}

        rounds_completed = 0
        for round_number in range(1, max_rounds + 1):
            rounds_completed = round_number
            fields = self.engine.scan_form_fields()
            round_fills = 0

            for field in fields:
                if not field.get("visible") or field.get("disabled"):
                    continue

                descriptor = self._descriptor_text(field)
                field_type = (field.get("type") or "").lower()
                tag = (field.get("tag") or "").lower()

                if field_type in {"hidden", "submit", "button", "search", "password"}:
                    continue

                if field_type == "file":
                    if resume_path and self._field_needs_input(field):
                        try:
                            self.engine.upload_file_by_index(int(field["index"]), resume_path)
                            uploaded_name = descriptor or f"file_{field['index']}"
                            if uploaded_name not in uploaded_files:
                                uploaded_files.append(uploaded_name)
                            field_expectations[int(field["index"])] = {
                                "descriptor": uploaded_name,
                                "kind": "file",
                                "required": bool(field.get("required")),
                            }
                            round_fills += 1
                        except Exception as exc:  # noqa: BLE001
                            self.logger.warning("Generic resume upload failed.", field=descriptor, error=repr(exc))
                    continue

                if field_type in {"checkbox", "radio"}:
                    choice_name = descriptor or f"choice_{field['index']}"
                    if choice_name not in skipped_fields:
                        skipped_fields.append(choice_name)
                    continue

                if not self._field_needs_input(field):
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
                    skipped_name = descriptor or f"field_{field['index']}"
                    if skipped_name not in skipped_fields:
                        skipped_fields.append(skipped_name)
                    continue

                try:
                    expected_value = value
                    if tag == "select":
                        option = self._pick_option(field.get("options", []), value)
                        if option:
                            self.engine.select_option_by_index(int(field["index"]), option)
                            expected_value = option
                        else:
                            skipped_name = descriptor or f"field_{field['index']}"
                            if skipped_name not in skipped_fields:
                                skipped_fields.append(skipped_name)
                            continue
                    else:
                        self.engine.fill_field_by_index(int(field["index"]), value)

                    field_name = descriptor or f"field_{field['index']}"
                    if field_name not in filled_fields:
                        filled_fields.append(field_name)
                    field_expectations[int(field["index"])] = {
                        "descriptor": field_name,
                        "expected_value": expected_value,
                        "kind": tag or field_type or "text",
                        "required": bool(field.get("required")),
                    }
                    round_fills += 1
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Generic field fill failed.", field=descriptor, error=repr(exc))
                    skipped_name = descriptor or f"field_{field['index']}"
                    if skipped_name not in skipped_fields:
                        skipped_fields.append(skipped_name)

            verification = self._verify_fields(field_expectations)
            verified_fields = verification["verified_fields"]
            unresolved_required_fields = verification["unresolved_required_fields"]
            unresolved_optional_fields = verification["unresolved_optional_fields"]

            self.logger.info(
                "Generic form fill round completed.",
                round=round_number,
                fills=round_fills,
                verified=len(verified_fields),
                unresolved_required=len(unresolved_required_fields),
                unresolved_optional=len(unresolved_optional_fields),
            )

            if round_fills == 0 or not unresolved_required_fields:
                break

        return FillResult(
            filled_fields=filled_fields,
            uploaded_files=uploaded_files,
            generated_answers=generated_answers,
            skipped_fields=skipped_fields,
            verified_fields=verified_fields,
            unresolved_required_fields=unresolved_required_fields,
            unresolved_optional_fields=unresolved_optional_fields,
            rounds_completed=rounds_completed,
            ready_to_advance=not unresolved_required_fields,
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

    def _field_needs_input(self, field: dict) -> bool:
        current_value = str(field.get("value", "") or "").strip()
        tag = str(field.get("tag", "") or "").lower()
        field_type = str(field.get("type", "") or "").lower()
        if tag == "select":
            return not current_value
        if field_type == "file":
            return True
        return not current_value

    def _verify_fields(self, field_expectations: dict[int, dict]) -> dict[str, list[str]]:
        latest_fields = {int(field["index"]): field for field in self.engine.scan_form_fields() if field.get("visible")}

        verified_fields: list[str] = []
        unresolved_required_fields: list[str] = []
        unresolved_optional_fields: list[str] = []

        for field_index, expectation in field_expectations.items():
            descriptor = expectation["descriptor"]
            field = latest_fields.get(field_index)
            if field is None:
                if descriptor not in verified_fields:
                    verified_fields.append(descriptor)
                continue

            if self._matches_expectation(field, expectation):
                if descriptor not in verified_fields:
                    verified_fields.append(descriptor)
                continue

            target = unresolved_required_fields if expectation.get("required") else unresolved_optional_fields
            if descriptor not in target:
                target.append(descriptor)

        return {
            "verified_fields": verified_fields,
            "unresolved_required_fields": unresolved_required_fields,
            "unresolved_optional_fields": unresolved_optional_fields,
        }

    def _matches_expectation(self, field: dict, expectation: dict) -> bool:
        kind = expectation.get("kind", "")
        if kind == "file":
            return True

        actual = str(field.get("value", "") or "").strip().lower()
        expected = str(expectation.get("expected_value", "") or "").strip().lower()
        if not expected:
            return bool(actual)
        if actual == expected:
            return True
        if expected in actual or actual in expected:
            return True
        return False
