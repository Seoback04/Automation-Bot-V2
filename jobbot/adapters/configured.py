from __future__ import annotations

from urllib.parse import quote_plus

from jobbot.adapters.base import JobPosting, JobSiteAdapter, PreparedApplication
from jobbot.automation.form_filler import FillResult, GenericFormFiller


class ConfiguredJobBoardAdapter(JobSiteAdapter):
    def __init__(self, engine, logger, site_config: dict) -> None:
        super().__init__(engine=engine, logger=logger)
        self.site_config = site_config
        self.site_name = site_config["site_name"]
        self.form_filler = GenericFormFiller(engine=engine, logger=logger)

    def open_search_page(self, query: str, location: str) -> None:
        template = self.site_config.get("search_url_template", "").strip()
        home_url = self.site_config.get("home_url", "").strip()
        if template:
            url = template.format(query=quote_plus(query), location=quote_plus(location))
        elif home_url:
            url = home_url
        else:
            raise RuntimeError(
                f"{self.site_name} does not define a search URL. Use Start URL or direct job URLs in the UI."
            )
        self.logger.info("Opening configured search page.", site=self.site_name, url=url)
        self.engine.goto(url)
        self.engine.sleep(2.0)

    def collect_job_links(self, max_jobs: int) -> list[str]:
        links = self.engine.attribute_values(self.site_config.get("job_link_selectors", []), "href", limit=max_jobs * 6)
        deduped: list[str] = []
        for link in links:
            if not link or link.startswith("javascript:"):
                continue
            if link not in deduped:
                deduped.append(link)
            if len(deduped) >= max_jobs:
                break
        return deduped

    def extract_job(self, url: str) -> JobPosting:
        title = self.engine.text_any(self.site_config.get("title_selectors", ["h1"]))
        company = self.engine.text_any(self.site_config.get("company_selectors", []))
        location = self.engine.text_any(self.site_config.get("location_selectors", []))
        description = "\n".join(self.engine.all_texts(self.site_config.get("description_selectors", []), limit=30))
        return JobPosting(
            site=self.site_name,
            url=url,
            title=title,
            company=company,
            location=location,
            description=description,
        )

    def prepare_application(self, job, profile, run_settings, resume_path, ai_client, cover_letter: str = "") -> PreparedApplication:
        apply_texts = self.site_config.get("apply_texts", [])
        apply_selectors = self._selectors_from_texts(apply_texts)

        if not (self.engine.try_click_any(apply_selectors, timeout_ms=4000) or self.engine.click_text(apply_texts, timeout_ms=4000)):
            return PreparedApplication(status="not_available", notes="No supported apply action found on the page.")

        self.engine.sleep(1.5)

        cover_letter = cover_letter or (
            ai_client.generate_cover_letter(job.to_dict(), profile) if run_settings.auto_generate_cover_letter else ""
        )
        submit_texts = self.site_config.get("submit_texts", [])
        next_texts = self.site_config.get("next_texts", [])
        submit_selectors = self._selectors_from_texts(submit_texts)
        fill_result = self.form_filler.fill_application_form(
            profile=profile,
            job=job.to_dict(),
            run_settings=run_settings,
            ai_client=ai_client,
            resume_path=resume_path,
            cover_letter=cover_letter,
        ) if run_settings.auto_fill_generic_forms else self._empty_fill_result()

        if run_settings.auto_fill_generic_forms and not fill_result.ready_to_advance:
            return PreparedApplication(
                status="review_ready",
                notes=(
                    "Required fields still need confirmation before moving forward: "
                    + ", ".join(fill_result.unresolved_required_fields[:8])
                ),
                submit_selectors=submit_selectors,
                generated_cover_letter=cover_letter,
                generated_answers=fill_result.generated_answers,
                metadata=fill_result.to_dict(),
            )

        for _ in range(5):
            if self.engine.exists_any(submit_selectors):
                return PreparedApplication(
                    status="review_ready",
                    notes="Application reached a final review or submit step.",
                    submit_selectors=submit_selectors,
                    generated_cover_letter=cover_letter,
                    generated_answers=fill_result.generated_answers,
                    metadata=fill_result.to_dict(),
                )

            if not (self.engine.click_text(next_texts, timeout_ms=2500) or self.engine.try_click_any(self._selectors_from_texts(next_texts), timeout_ms=2500)):
                break

            self.engine.sleep(1.2)
            fill_result = self.form_filler.fill_application_form(
                profile=profile,
                job=job.to_dict(),
                run_settings=run_settings,
                ai_client=ai_client,
                resume_path=resume_path,
                cover_letter=cover_letter,
            ) if run_settings.auto_fill_generic_forms else fill_result

            if run_settings.auto_fill_generic_forms and not fill_result.ready_to_advance:
                return PreparedApplication(
                    status="review_ready",
                    notes=(
                        "Moved to a new step, but required fields still need confirmation: "
                        + ", ".join(fill_result.unresolved_required_fields[:8])
                    ),
                    submit_selectors=submit_selectors,
                    generated_cover_letter=cover_letter,
                    generated_answers=fill_result.generated_answers,
                    metadata=fill_result.to_dict(),
                )

        return PreparedApplication(
            status="review_ready",
            notes="Generic compatibility mode prepared the form for manual review.",
            submit_selectors=submit_selectors,
            generated_cover_letter=cover_letter,
            generated_answers=fill_result.generated_answers,
            metadata=fill_result.to_dict(),
        )

    def _empty_fill_result(self) -> FillResult:
        return FillResult([], [], {}, [], [], [], [], 0, True)

    def _selectors_from_texts(self, texts: list[str]) -> list[str]:
        selectors: list[str] = []
        for text in texts:
            selectors.extend(
                [
                    f"xpath=//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
                    f"xpath=//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
                    f"xpath=//*[@role='button' and contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
                    f"xpath=//*[@aria-label and contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]",
                ]
            )
        return selectors
