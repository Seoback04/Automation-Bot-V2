from __future__ import annotations

from pathlib import Path

from jobbot.automation.engines.base import BrowserEngine


class PlaywrightEngine(BrowserEngine):
    def __init__(self, settings, logger) -> None:
        super().__init__(settings, logger)
        self.playwright = None
        self.context = None
        self.page = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        launch_args = {"headless": self.settings.headless, "slow_mo": self.settings.slow_mo_ms}
        executable = Path(self.settings.browser_binary_path)
        if executable.exists():
            launch_args["executable_path"] = str(executable)

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.settings.browser_user_data_dir,
            **launch_args,
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(self.settings.timeout_ms)

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
        if self.playwright is not None:
            self.playwright.stop()

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def current_url(self) -> str:
        return self.page.url

    def click_any(self, selectors: list[str], timeout_ms: int | None = None) -> str:
        last_error: Exception | None = None
        for _ in range(2):
            for selector in selectors:
                try:
                    locator = self.page.locator(self._selector(selector)).first
                    locator.wait_for(state="visible", timeout=timeout_ms or self.settings.timeout_ms)
                    locator.click()
                    return selector
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.sleep(0.5)
        raise RuntimeError(f"Unable to click selectors: {selectors}") from last_error

    def fill_any(self, selectors: list[str], value: str, timeout_ms: int | None = None) -> str:
        last_error: Exception | None = None
        for _ in range(2):
            for selector in selectors:
                try:
                    locator = self.page.locator(self._selector(selector)).first
                    locator.wait_for(state="visible", timeout=timeout_ms or self.settings.timeout_ms)
                    locator.click()
                    locator.fill(value)
                    return selector
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.sleep(0.5)
        raise RuntimeError(f"Unable to fill selectors: {selectors}") from last_error

    def upload_file(self, selectors: list[str], file_path: str) -> str:
        last_error: Exception | None = None
        for _ in range(2):
            for selector in selectors:
                try:
                    self.page.locator(self._selector(selector)).first.set_input_files(file_path)
                    return selector
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.sleep(0.5)
        raise RuntimeError(f"Unable to upload file with selectors: {selectors}") from last_error

    def exists_any(self, selectors: list[str]) -> bool:
        for selector in selectors:
            try:
                if self.page.locator(self._selector(selector)).count() > 0:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def text_any(self, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                text = self.page.locator(self._selector(selector)).first.text_content(timeout=2000) or ""
                if text.strip():
                    return text.strip()
            except Exception:  # noqa: BLE001
                continue
        return ""

    def all_texts(self, selectors: list[str], limit: int = 10) -> list[str]:
        values: list[str] = []
        for selector in selectors:
            try:
                texts = self.page.locator(self._selector(selector)).all_text_contents()
                values.extend([text.strip() for text in texts if text.strip()])
            except Exception:  # noqa: BLE001
                continue
            if values:
                break
        return values[:limit]

    def attribute_values(self, selectors: list[str], attribute: str, limit: int = 10) -> list[str]:
        values: list[str] = []
        for selector in selectors:
            try:
                locator = self.page.locator(self._selector(selector))
                count = min(locator.count(), limit)
                for index in range(count):
                    value = locator.nth(index).get_attribute(attribute)
                    if value:
                        values.append(value)
            except Exception:  # noqa: BLE001
                continue
            if values:
                break
        return values[:limit]

    def screenshot(self, path: str | Path) -> None:
        self.page.screenshot(path=str(path), full_page=True)

    def _selector(self, selector: str) -> str:
        if selector.startswith("xpath="):
            return selector
        if selector.startswith("//"):
            return f"xpath={selector}"
        return selector
