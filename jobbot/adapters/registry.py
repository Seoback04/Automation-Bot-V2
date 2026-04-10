from __future__ import annotations

from jobbot.adapters.configured import ConfiguredJobBoardAdapter
from jobbot.adapters.base import JobSiteAdapter
from jobbot.adapters.linkedin import LinkedInAdapter
from jobbot.adapters.seek import SeekAdapter


SITE_CONFIGS: dict[str, dict] = {
    "generic": {
        "site_name": "generic",
        "home_url": "",
        "job_link_selectors": [
            "a[href*='/job/']",
            "a[href*='/jobs/']",
            "a[data-automation*='job']",
            "xpath=//a[contains(@href, 'job')]",
        ],
        "title_selectors": ["h1", "[data-testid*='job']", ".job-title", ".posting-title"],
        "company_selectors": [
            "[data-testid*='company']",
            ".company",
            ".employer",
            "xpath=//*[contains(@class, 'company')]",
        ],
        "location_selectors": [
            "[data-testid*='location']",
            ".location",
            "xpath=//*[contains(@class, 'location')]",
        ],
        "description_selectors": [
            "main *",
            "article *",
            "[data-testid*='description'] *",
            ".description *",
        ],
        "apply_texts": ["easy apply", "quick apply", "apply now", "apply", "start application"],
        "next_texts": ["continue", "next", "review", "save and continue"],
        "submit_texts": ["submit application", "submit", "send application", "finish"],
    },
    "indeed": {
        "site_name": "indeed",
        "search_url_template": "https://www.indeed.com/jobs?q={query}&l={location}",
        "job_link_selectors": [
            "a.jcs-JobTitle",
            "a[href*='/viewjob']",
            "a[data-jk]",
        ],
        "title_selectors": ["h1", "[data-testid='jobsearch-JobInfoHeader-title']"],
        "company_selectors": ["[data-testid='inlineHeader-companyName']", "[data-company-name='true']"],
        "location_selectors": ["[data-testid='job-location']", ".jobsearch-JobInfoHeader-subtitle"],
        "description_selectors": ["#jobDescriptionText *", ".jobsearch-JobComponent-description *"],
        "apply_texts": ["apply now", "apply on company site", "easy apply", "apply"],
        "next_texts": ["continue", "next", "review"],
        "submit_texts": ["submit application", "submit", "finish"],
    },
    "student_job_search": {
        "site_name": "student_job_search",
        "home_url": "https://www.sjs.co.nz/search/jobs",
        "job_link_selectors": ["a[href*='/job/']", "xpath=//a[contains(@href, '/job/')]"],
        "title_selectors": ["h1", ".job-title"],
        "company_selectors": [".company", "[class*='company']"],
        "location_selectors": [".location", "[class*='location']"],
        "description_selectors": ["main *", "article *", ".job-description *"],
        "apply_texts": ["apply now", "apply", "express interest"],
        "next_texts": ["continue", "next", "review"],
        "submit_texts": ["submit", "send application", "finish"],
    },
    "sidekicker": {
        "site_name": "sidekicker",
        "home_url": "https://sidekicker.com/nz/jobs",
        "job_link_selectors": ["a[href*='/jobs/']", "xpath=//a[contains(@href, 'job')]"],
        "title_selectors": ["h1", ".job-title"],
        "company_selectors": [".company", "[class*='company']"],
        "location_selectors": [".location", "[class*='location']"],
        "description_selectors": ["main *", "article *", ".job-description *"],
        "apply_texts": ["apply now", "apply", "accept shift"],
        "next_texts": ["continue", "next", "review"],
        "submit_texts": ["submit", "finish", "send application"],
    },
    "zeil": {
        "site_name": "zeil",
        "home_url": "",
        "job_link_selectors": ["a[href*='/job']", "a[href*='/jobs']"],
        "title_selectors": ["h1", ".job-title"],
        "company_selectors": [".company", "[class*='company']"],
        "location_selectors": [".location", "[class*='location']"],
        "description_selectors": ["main *", "article *", ".job-description *"],
        "apply_texts": ["apply now", "apply", "easy apply"],
        "next_texts": ["continue", "next", "review"],
        "submit_texts": ["submit", "finish", "send application"],
    },
}

ADAPTERS: dict[str, type[JobSiteAdapter]] = {
    "linkedin": LinkedInAdapter,
    "seek": SeekAdapter,
}


def create_adapter(site_name: str, engine, logger) -> JobSiteAdapter:
    normalized = site_name.lower()
    alias_map = {
        "sjs": "student_job_search",
        "student job search": "student_job_search",
        "zeal": "zeil",
    }
    normalized = alias_map.get(normalized, normalized)

    if normalized in ADAPTERS:
        return ADAPTERS[normalized](engine=engine, logger=logger)
    if normalized in SITE_CONFIGS:
        return ConfiguredJobBoardAdapter(engine=engine, logger=logger, site_config=SITE_CONFIGS[normalized])
    raise ValueError(f"Unsupported site adapter: {site_name}")


def supported_site_names() -> list[str]:
    return sorted(set(list(ADAPTERS.keys()) + list(SITE_CONFIGS.keys())))
