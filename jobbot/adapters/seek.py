from __future__ import annotations

from urllib.parse import quote_plus

from jobbot.adapters.base import JobPosting, JobSiteAdapter, PreparedApplication
from jobbot.automation.form_filler import FillResult, GenericFormFiller


class SeekAdapter(JobSiteAdapter):
    site_name = "seek"

    JOB_LINK_SELECTORS = [
        "a[data-automation='jobTitle']",
        "xpath=//a[contains(@href, '/job/')]",
    ]
    APPLY_SELECTORS = [
        "a[data-automation='job-detail-apply']",
        "button[data-automation='job-detail-apply']",
        "xpath=//a[contains(normalize-space(.), 'Apply')]",
        "xpath=//button[contains(normalize-space(.), 'Apply')]",
    ]
    SUBMIT_SELECTORS = [
        "xpath=//button[contains(normalize-space(.), 'Submit')]",
        "xpath=//button[contains(normalize-space(.), 'Send application')]",
    ]
    NEXT_SELECTORS = [
        "xpath=//button[contains(normalize-space(.), 'Continue')]",
        "xpath=//button[contains(normalize-space(.), 'Next')]",
        "xpath=//button[contains(normalize-space(.), 'Review')]",
    ]

    def open_search_page(self, query: str, location: str) -> None:
        url = "https://www.seek.co.nz/jobs" f"?keywords={quote_plus(query)}&where={quote_plus(location)}"
        self.logger.info("Opening Seek search page.", query=query, location=location)
        self.engine.goto(url)
        self.engine.sleep(2.0)

    def collect_job_links(self, max_jobs: int) -> list[str]:
        links = self.engine.attribute_values(self.JOB_LINK_SELECTORS, "href", limit=max_jobs * 4)
        deduped: list[str] = []
        for link in links:
            if "/job/" not in link:
                continue
            if link not in deduped:
                deduped.append(link)
            if len(deduped) >= max_jobs:
                break
        return deduped

    def extract_job(self, url: str) -> JobPosting:
        title = self.engine.text_any(["h1", "[data-automation='job-detail-title']"])
        company = self.engine.text_any(
            [
                "[data-automation='advertiser-name']",
                "xpath=//span[contains(@data-automation, 'company')]",
            ]
        )
        location = self.engine.text_any(
            [
                "[data-automation='job-detail-location']",
                "xpath=//span[contains(@data-automation, 'location')]",
            ]
        )
        description = "\n".join(
            self.engine.all_texts(
                [
                    "[data-automation='jobAdDetails'] *",
                    "xpath=//div[contains(@data-automation, 'jobAdDetails')]//*",
                ],
                limit=25,
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
        if not self.engine.try_click_any(self.APPLY_SELECTORS, timeout_ms=5000):
            return PreparedApplication(status="not_available", notes="Seek apply button not found.")

        self.engine.sleep(1.5)
        form_filler = GenericFormFiller(self.engine, self.logger)
        self._fill_common_fields(profile)

        generated_cover_letter = ""
        if run_settings.auto_generate_cover_letter:
            generated_cover_letter = ai_client.generate_cover_letter(job.to_dict(), profile)
            self.engine.try_fill_any(
                [
                    "textarea[aria-label*='Cover letter']",
                    "textarea[name*='cover']",
                    "textarea[id*='cover']",
                ],
                generated_cover_letter,
                timeout_ms=2000,
            )

        if resume_path:
            try:
                self.engine.upload_file(["input[type='file']"], resume_path)
            except Exception:  # noqa: BLE001
                self.logger.warning("Resume upload did not match the current Seek form.", resume_path=resume_path)

        generic_fill_result = form_filler.fill_application_form(
            profile=profile,
            job=job.to_dict(),
            run_settings=run_settings,
            ai_client=ai_client,
            resume_path=resume_path,
            cover_letter=generated_cover_letter,
        ) if run_settings.auto_fill_generic_forms else FillResult([], [], {}, [])

        for _ in range(4):
            if self.engine.exists_any(self.SUBMIT_SELECTORS):
                return PreparedApplication(
                    status="review_ready",
                    notes="Reached the final Seek review step.",
                    submit_selectors=self.SUBMIT_SELECTORS,
                    generated_cover_letter=generated_cover_letter,
                    generated_answers=generic_fill_result.generated_answers,
                    metadata=generic_fill_result.to_dict(),
                )
            if not self.engine.try_click_any(self.NEXT_SELECTORS, timeout_ms=3000):
                break
            self.engine.sleep(1.0)
            self._fill_common_fields(profile)
            generic_fill_result = form_filler.fill_application_form(
                profile=profile,
                job=job.to_dict(),
                run_settings=run_settings,
                ai_client=ai_client,
                resume_path=resume_path,
                cover_letter=generated_cover_letter,
            ) if run_settings.auto_fill_generic_forms else generic_fill_result

        return PreparedApplication(
            status="review_ready",
            notes="Seek application prepared for manual review.",
            submit_selectors=self.SUBMIT_SELECTORS,
            generated_cover_letter=generated_cover_letter,
            generated_answers=generic_fill_result.generated_answers,
            metadata=generic_fill_result.to_dict(),
        )

    def _fill_common_fields(self, profile) -> None:
        field_map = {
            profile.full_name: ["input[aria-label*='Name']", "input[name*='name']"],
            profile.email: ["input[aria-label*='Email']", "input[name*='email']"],
            profile.phone: ["input[aria-label*='Phone']", "input[name*='phone']"],
            profile.location: ["input[aria-label*='Location']", "input[name*='location']"],
        }
        for value, selectors in field_map.items():
            if value:
                self.engine.try_fill_any(selectors, value, timeout_ms=2000)
