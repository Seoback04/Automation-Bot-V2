from __future__ import annotations

from urllib.parse import quote_plus

from jobbot.adapters.base import JobPosting, JobSiteAdapter, PreparedApplication
from jobbot.automation.form_filler import FillResult, GenericFormFiller


class LinkedInAdapter(JobSiteAdapter):
    site_name = "linkedin"

    JOB_LINK_SELECTORS = [
        "a.job-card-container__link",
        "a.job-card-list__title",
        "a.base-card__full-link",
        "xpath=//a[contains(@href, '/jobs/view/')]",
    ]
    EASY_APPLY_SELECTORS = [
        "button.jobs-apply-button",
        "button[aria-label*='Easy Apply']",
        "xpath=//button[contains(normalize-space(.), 'Easy Apply')]",
    ]
    SUBMIT_SELECTORS = [
        "button[aria-label*='Submit application']",
        "xpath=//button[contains(normalize-space(.), 'Submit application')]",
        "xpath=//button[contains(normalize-space(.), 'Submit')]",
    ]
    NEXT_SELECTORS = [
        "xpath=//button[contains(normalize-space(.), 'Next')]",
        "xpath=//button[contains(normalize-space(.), 'Review')]",
        "xpath=//button[contains(normalize-space(.), 'Continue')]",
    ]

    def open_search_page(self, query: str, location: str) -> None:
        url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(query)}&location={quote_plus(location)}"
        )
        self.logger.info("Opening LinkedIn search page.", query=query, location=location)
        self.engine.goto(url)
        self.engine.sleep(2.0)

    def collect_job_links(self, max_jobs: int) -> list[str]:
        links = self.engine.attribute_values(self.JOB_LINK_SELECTORS, "href", limit=max_jobs * 4)
        deduped: list[str] = []
        for link in links:
            clean_link = link.split("?")[0]
            if "/jobs/view/" not in clean_link:
                continue
            if clean_link not in deduped:
                deduped.append(clean_link)
            if len(deduped) >= max_jobs:
                break
        return deduped

    def extract_job(self, url: str) -> JobPosting:
        title = self.engine.text_any(["h1", ".job-details-jobs-unified-top-card__job-title", ".top-card-layout__title"])
        company = self.engine.text_any(
            [
                ".job-details-jobs-unified-top-card__company-name",
                ".topcard__org-name-link",
                "a.topcard__org-name-link",
            ]
        )
        location = self.engine.text_any(
            [
                ".job-details-jobs-unified-top-card__primary-description-container",
                ".topcard__flavor--bullet",
                ".jobs-unified-top-card__subtitle-primary-grouping",
            ]
        )
        description = "\n".join(
            self.engine.all_texts(
                [
                    ".jobs-description__content",
                    ".jobs-box__html-content",
                    ".show-more-less-html__markup",
                ],
                limit=20,
            )
        )
        return JobPosting(
            site=self.site_name,
            url=url,
            title=title,
            company=company,
            location=location,
            description=description,
        )

    def prepare_application(self, job, profile, run_settings, resume_path, ai_client) -> PreparedApplication:
        if not self.engine.try_click_any(self.EASY_APPLY_SELECTORS, timeout_ms=5000):
            return PreparedApplication(status="not_available", notes="Easy Apply not found.")

        self.engine.sleep(1.5)
        form_filler = GenericFormFiller(self.engine, self.logger)
        self._fill_common_fields(profile)

        generated_cover_letter = ""
        if run_settings.auto_generate_cover_letter:
            generated_cover_letter = ai_client.generate_cover_letter(job.to_dict(), profile)
            self._fill_cover_letter(generated_cover_letter)

        if resume_path:
            try:
                self.engine.upload_file(["input[type='file']"], resume_path)
            except Exception:  # noqa: BLE001
                self.logger.warning("Resume upload did not match the current LinkedIn form.", resume_path=resume_path)

        generated_answers = self._apply_custom_answers(profile, ai_client, job)
        generic_fill_result = form_filler.fill_application_form(
            profile=profile,
            job=job.to_dict(),
            run_settings=run_settings,
            ai_client=ai_client,
            resume_path=resume_path,
            cover_letter=generated_cover_letter,
        ) if run_settings.auto_fill_generic_forms else self._empty_fill_result()
        generated_answers.update(generic_fill_result.generated_answers)

        if run_settings.auto_fill_generic_forms and not generic_fill_result.ready_to_advance:
            return PreparedApplication(
                status="review_ready",
                notes=(
                    "LinkedIn form needs confirmation before moving forward: "
                    + ", ".join(generic_fill_result.unresolved_required_fields[:8])
                ),
                submit_selectors=self.SUBMIT_SELECTORS,
                generated_cover_letter=generated_cover_letter,
                generated_answers=generated_answers,
                metadata=generic_fill_result.to_dict(),
            )

        for _ in range(4):
            if self.engine.exists_any(self.SUBMIT_SELECTORS):
                return PreparedApplication(
                    status="review_ready",
                    notes="Reached the final LinkedIn review step.",
                    submit_selectors=self.SUBMIT_SELECTORS,
                    generated_cover_letter=generated_cover_letter,
                    generated_answers=generated_answers,
                    metadata=generic_fill_result.to_dict(),
                )
            if not self.engine.try_click_any(self.NEXT_SELECTORS, timeout_ms=3000):
                break
            self.engine.sleep(1.2)
            self._fill_common_fields(profile)
            if generated_cover_letter:
                self._fill_cover_letter(generated_cover_letter)
            generic_fill_result = form_filler.fill_application_form(
                profile=profile,
                job=job.to_dict(),
                run_settings=run_settings,
                ai_client=ai_client,
                resume_path=resume_path,
                cover_letter=generated_cover_letter,
            ) if run_settings.auto_fill_generic_forms else generic_fill_result
            generated_answers.update(generic_fill_result.generated_answers)

            if run_settings.auto_fill_generic_forms and not generic_fill_result.ready_to_advance:
                return PreparedApplication(
                    status="review_ready",
                    notes=(
                        "LinkedIn form still has required fields to confirm: "
                        + ", ".join(generic_fill_result.unresolved_required_fields[:8])
                    ),
                    submit_selectors=self.SUBMIT_SELECTORS,
                    generated_cover_letter=generated_cover_letter,
                    generated_answers=generated_answers,
                    metadata=generic_fill_result.to_dict(),
                )

        return PreparedApplication(
            status="review_ready",
            notes="LinkedIn apply dialog prepared for manual review.",
            submit_selectors=self.SUBMIT_SELECTORS,
            generated_cover_letter=generated_cover_letter,
            generated_answers=generated_answers,
            metadata=generic_fill_result.to_dict(),
        )

    def _empty_fill_result(self) -> FillResult:
        return FillResult([], [], {}, [], [], [], [], 0, True)

    def _fill_common_fields(self, profile) -> None:
        names = profile.full_name.split()
        first_name = names[0] if names else ""
        last_name = " ".join(names[1:]) if len(names) > 1 else ""

        field_map = {
            profile.email: ["input[id*='emailAddress']", "input[aria-label*='Email']", "input[name*='email']"],
            profile.phone: ["input[id*='phoneNumber']", "input[aria-label*='Phone']", "input[name*='phone']"],
            profile.location: ["input[aria-label*='City']", "input[aria-label*='Location']", "input[name*='city']"],
            first_name: ["input[aria-label*='First name']", "input[name*='firstName']"],
            last_name: ["input[aria-label*='Last name']", "input[name*='lastName']"],
        }
        for value, selectors in field_map.items():
            if value:
                self.engine.try_fill_any(selectors, value, timeout_ms=2000)

    def _fill_cover_letter(self, cover_letter: str) -> None:
        if not cover_letter:
            return
        self.engine.try_fill_any(
            [
                "textarea[aria-label*='Cover letter']",
                "textarea[name*='coverLetter']",
                "textarea[id*='coverLetter']",
            ],
            cover_letter,
            timeout_ms=2000,
        )

    def _apply_custom_answers(self, profile, ai_client, job) -> dict[str, str]:
        applied: dict[str, str] = {}
        common_questions = {
            "visa": [
                "textarea[aria-label*='visa']",
                "input[aria-label*='visa']",
                "textarea[aria-label*='authorized']",
                "input[aria-label*='authorized']",
            ],
            "salary": [
                "textarea[aria-label*='salary']",
                "input[aria-label*='salary']",
                "textarea[aria-label*='compensation']",
                "input[aria-label*='compensation']",
            ],
        }
        for keyword, selectors in common_questions.items():
            answer = profile.custom_answers.get(keyword) or ai_client.answer_application_question(keyword, job.to_dict(), profile)
            if answer and self.engine.try_fill_any(selectors, answer, timeout_ms=1500):
                applied[keyword] = answer
        return applied
