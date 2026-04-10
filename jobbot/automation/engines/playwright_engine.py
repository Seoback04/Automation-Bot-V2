from __future__ import annotations

from pathlib import Path

from jobbot.automation.engines.base import BrowserEngine


class PlaywrightEngine(BrowserEngine):
    def __init__(self, settings, logger) -> None:
        super().__init__(settings, logger)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.attached = False

    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        if self.settings.attach_to_existing_browser:
            self.browser = self.playwright.chromium.connect_over_cdp(self.settings.remote_debugging_url)
            self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.attached = True
        else:
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
        if self.context is not None and not self.attached and not self.settings.keep_browser_open:
            self.context.close()
        if self.playwright is not None:
            self.playwright.stop()

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def current_url(self) -> str:
        return self.page.url

    def current_title(self) -> str:
        return self.page.title()

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

    def scan_form_fields(self) -> list[dict]:
        return self.page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('input, textarea, select'));
              const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
              };
              const getLabel = (el) => {
                const explicit = el.labels && el.labels.length ? Array.from(el.labels).map(label => label.innerText || label.textContent || '').join(' ') : '';
                if (explicit.trim()) return explicit.trim();
                if (el.id) {
                  const label = document.querySelector(`label[for="${el.id}"]`);
                  if (label) return (label.innerText || label.textContent || '').trim();
                }
                const parentLabel = el.closest('label');
                if (parentLabel) return (parentLabel.innerText || parentLabel.textContent || '').trim();
                const container = el.closest('div, fieldset, section, form');
                if (!container) return '';
                const nearby = container.querySelector('label, legend, span, p');
                return nearby ? (nearby.innerText || nearby.textContent || '').trim() : '';
              };
              return nodes.map((el, index) => ({
                index,
                tag: el.tagName.toLowerCase(),
                type: (el.getAttribute('type') || '').toLowerCase(),
                name: el.getAttribute('name') || '',
                id: el.id || '',
                placeholder: el.getAttribute('placeholder') || '',
                aria_label: el.getAttribute('aria-label') || '',
                autocomplete: el.getAttribute('autocomplete') || '',
                title: el.getAttribute('title') || '',
                required: el.required,
                disabled: el.disabled,
                visible: visible(el),
                label: getLabel(el),
                accept: el.getAttribute('accept') || '',
                value: el.value || '',
                options: el.tagName.toLowerCase() === 'select'
                  ? Array.from(el.options).map(option => option.textContent || option.value || '').slice(0, 25)
                  : []
              }));
            }
            """
        )

    def fill_field_by_index(self, field_index: int, value: str) -> bool:
        locator = self.page.locator("input, textarea, select").nth(field_index)
        locator.scroll_into_view_if_needed()
        tag_name = (locator.evaluate("(node) => node.tagName.toLowerCase()") or "").lower()
        if tag_name == "select":
            locator.select_option(label=value)
        else:
            locator.click()
            locator.fill(value)
        return True

    def upload_file_by_index(self, field_index: int, file_path: str) -> bool:
        locator = self.page.locator("input, textarea, select").nth(field_index)
        locator.set_input_files(file_path)
        return True

    def select_option_by_index(self, field_index: int, value: str) -> bool:
        locator = self.page.locator("input, textarea, select").nth(field_index)
        option_values = locator.evaluate(
            """
            (node) => Array.from(node.options || []).map(option => ({
              label: option.label || option.textContent || '',
              value: option.value || ''
            }))
            """
        )
        selected = None
        desired = value.strip().lower()
        for option in option_values:
            label = str(option.get("label", "")).strip()
            option_value = str(option.get("value", "")).strip()
            if label.lower() == desired or option_value.lower() == desired:
                selected = option
                break
        if selected is None:
            for option in option_values:
                label = str(option.get("label", "")).strip().lower()
                option_value = str(option.get("value", "")).strip().lower()
                if desired and (desired in label or desired in option_value or label in desired or option_value in desired):
                    selected = option
                    break
        if selected is None:
            raise RuntimeError(f"No matching select option for value: {value}")
        option_value = str(selected.get("value", "")).strip()
        option_label = str(selected.get("label", "")).strip()
        if option_value:
            locator.select_option(value=option_value)
        elif option_label:
            locator.select_option(label=option_label)
        else:
            raise RuntimeError(f"Resolved select option is empty for value: {value}")
        return True

    def _selector(self, selector: str) -> str:
        if selector.startswith("xpath="):
            return selector
        if selector.startswith("//"):
            return f"xpath={selector}"
        return selector
