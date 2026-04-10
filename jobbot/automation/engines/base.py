from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path

from jobbot.config.models import BrowserSettings
from jobbot.utils.run_logger import RunLogger


class BrowserEngine(ABC):
    def __init__(self, settings: BrowserSettings, logger: RunLogger) -> None:
        self.settings = settings
        self.logger = logger

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def goto(self, url: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def current_url(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def click_any(self, selectors: list[str], timeout_ms: int | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def fill_any(self, selectors: list[str], value: str, timeout_ms: int | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def upload_file(self, selectors: list[str], file_path: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exists_any(self, selectors: list[str]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def text_any(self, selectors: list[str]) -> str:
        raise NotImplementedError

    @abstractmethod
    def all_texts(self, selectors: list[str], limit: int = 10) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def attribute_values(self, selectors: list[str], attribute: str, limit: int = 10) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def screenshot(self, path: str | Path) -> None:
        raise NotImplementedError

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def click_text(self, texts: list[str], timeout_ms: int | None = None) -> bool:
        selectors: list[str] = []
        for text in texts:
            selectors.append(f"xpath=//button[contains(normalize-space(.), '{text}')]")
            selectors.append(f"xpath=//*[@role='button' and contains(normalize-space(.), '{text}')]")
            selectors.append(f"xpath=//a[contains(normalize-space(.), '{text}')]")
            selectors.append(f"xpath=//*[@aria-label and contains(@aria-label, '{text}')]")
        return self.try_click_any(selectors, timeout_ms=timeout_ms)

    def try_click_any(self, selectors: list[str], timeout_ms: int | None = None) -> bool:
        try:
            self.click_any(selectors, timeout_ms=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            return False

    def try_fill_any(self, selectors: list[str], value: str, timeout_ms: int | None = None) -> bool:
        try:
            self.fill_any(selectors, value, timeout_ms=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            return False
