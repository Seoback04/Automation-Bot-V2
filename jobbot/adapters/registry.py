from __future__ import annotations

from jobbot.adapters.base import JobSiteAdapter
from jobbot.adapters.linkedin import LinkedInAdapter
from jobbot.adapters.seek import SeekAdapter


ADAPTERS: dict[str, type[JobSiteAdapter]] = {
    "linkedin": LinkedInAdapter,
    "seek": SeekAdapter,
}


def create_adapter(site_name: str, engine, logger) -> JobSiteAdapter:
    try:
        adapter_class = ADAPTERS[site_name.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported site adapter: {site_name}") from exc
    return adapter_class(engine=engine, logger=logger)
