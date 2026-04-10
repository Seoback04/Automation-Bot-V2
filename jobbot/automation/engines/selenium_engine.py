from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from jobbot.automation.engines.base import BrowserEngine


class SeleniumEngine(BrowserEngine):
    def __init__(self, settings, logger) -> None:
        super().__init__(settings, logger)
        self.driver = None
        self.attached = False

    def start(self) -> None:
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        if self.settings.browser_user_data_dir:
            options.add_argument(f"--user-data-dir={self.settings.browser_user_data_dir}")
        if self.settings.headless:
            options.add_argument("--headless=new")

        binary_path = Path(self.settings.browser_binary_path)
        if binary_path.exists():
            options.binary_location = str(binary_path)

        if self.settings.attach_to_existing_browser:
            debugger_address = self.settings.remote_debugging_url.replace("http://", "").replace("https://", "")
            options.debugger_address = debugger_address
            self.attached = True

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(max(30, int(self.settings.timeout_ms / 1000)))

    def close(self) -> None:
        if self.driver is not None and not self.attached and not self.settings.keep_browser_open:
            self.driver.quit()

    def goto(self, url: str) -> None:
        self.driver.get(url)

    def current_url(self) -> str:
        return self.driver.current_url

    def current_title(self) -> str:
        return self.driver.title

    def click_any(self, selectors: list[str], timeout_ms: int | None = None) -> str:
        last_error: Exception | None = None
        wait_seconds = max(2, int((timeout_ms or self.settings.timeout_ms) / 1000))
        for _ in range(2):
            for selector in selectors:
                try:
                    by, value = self._selector(selector)
                    element = WebDriverWait(self.driver, wait_seconds).until(EC.element_to_be_clickable((by, value)))
                    element.click()
                    return selector
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.sleep(0.5)
        raise RuntimeError(f"Unable to click selectors: {selectors}") from last_error

    def fill_any(self, selectors: list[str], value: str, timeout_ms: int | None = None) -> str:
        last_error: Exception | None = None
        wait_seconds = max(2, int((timeout_ms or self.settings.timeout_ms) / 1000))
        for _ in range(2):
            for selector in selectors:
                try:
                    by, locator = self._selector(selector)
                    element = WebDriverWait(self.driver, wait_seconds).until(
                        EC.visibility_of_element_located((by, locator))
                    )
                    element.clear()
                    element.send_keys(value)
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
                    by, locator = self._selector(selector)
                    self.driver.find_element(by, locator).send_keys(file_path)
                    return selector
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
            self.sleep(0.5)
        raise RuntimeError(f"Unable to upload file with selectors: {selectors}") from last_error

    def exists_any(self, selectors: list[str]) -> bool:
        for selector in selectors:
            try:
                by, locator = self._selector(selector)
                if self.driver.find_elements(by, locator):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    def text_any(self, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                by, locator = self._selector(selector)
                text = self.driver.find_element(by, locator).text.strip()
                if text:
                    return text
            except Exception:  # noqa: BLE001
                continue
        return ""

    def all_texts(self, selectors: list[str], limit: int = 10) -> list[str]:
        values: list[str] = []
        for selector in selectors:
            try:
                by, locator = self._selector(selector)
                elements = self.driver.find_elements(by, locator)
                values.extend([element.text.strip() for element in elements if element.text.strip()])
            except Exception:  # noqa: BLE001
                continue
            if values:
                break
        return values[:limit]

    def attribute_values(self, selectors: list[str], attribute: str, limit: int = 10) -> list[str]:
        values: list[str] = []
        for selector in selectors:
            try:
                by, locator = self._selector(selector)
                for element in self.driver.find_elements(by, locator)[:limit]:
                    value = element.get_attribute(attribute)
                    if value:
                        values.append(value)
            except Exception:  # noqa: BLE001
                continue
            if values:
                break
        return values[:limit]

    def screenshot(self, path: str | Path) -> None:
        self.driver.save_screenshot(str(path))

    def scan_form_fields(self) -> list[dict]:
        return self.driver.execute_script(
            """
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
              required: !!el.required,
              disabled: !!el.disabled,
              visible: visible(el),
              label: getLabel(el),
              accept: el.getAttribute('accept') || '',
              value: el.value || '',
              options: el.tagName.toLowerCase() === 'select'
                ? Array.from(el.options).map(option => option.textContent || option.value || '').slice(0, 25)
                : []
            }));
            """
        )

    def fill_field_by_index(self, field_index: int, value: str) -> bool:
        element = self.driver.execute_script(
            "return document.querySelectorAll('input, textarea, select')[arguments[0]];",
            field_index,
        )
        tag_name = (element.tag_name or "").lower()
        if tag_name == "select":
            from selenium.webdriver.support.ui import Select

            Select(element).select_by_visible_text(value)
        else:
            element.clear()
            element.send_keys(value)
        return True

    def upload_file_by_index(self, field_index: int, file_path: str) -> bool:
        element = self.driver.execute_script(
            "return document.querySelectorAll('input, textarea, select')[arguments[0]];",
            field_index,
        )
        element.send_keys(file_path)
        return True

    def select_option_by_index(self, field_index: int, value: str) -> bool:
        from selenium.webdriver.support.ui import Select

        element = self.driver.execute_script(
            "return document.querySelectorAll('input, textarea, select')[arguments[0]];",
            field_index,
        )
        select = Select(element)
        desired = value.strip().lower()
        matched_text = ""
        for option in select.options:
            text = option.text.strip()
            option_value = (option.get_attribute("value") or "").strip()
            if text.lower() == desired or option_value.lower() == desired:
                matched_text = text
                break
        if not matched_text:
            for option in select.options:
                text = option.text.strip().lower()
                option_value = (option.get_attribute("value") or "").strip().lower()
                if desired and (desired in text or desired in option_value or text in desired or option_value in desired):
                    matched_text = option.text.strip()
                    break
        if not matched_text:
            raise RuntimeError(f"No matching select option for value: {value}")
        select.select_by_visible_text(matched_text)
        return True

    def _selector(self, selector: str) -> tuple[str, str]:
        if selector.startswith("xpath="):
            return By.XPATH, selector.removeprefix("xpath=")
        if selector.startswith("//"):
            return By.XPATH, selector
        return By.CSS_SELECTOR, selector
