from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
STREAMLIT_APP = ROOT_DIR / "streamlit_app.py"
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
DATA_DIR = ROOT_DIR / "data"
LAUNCHER_LOG_DIR = DATA_DIR / "logs" / "launcher"
STREAMLIT_LOG_FILE = LAUNCHER_LOG_DIR / "streamlit.log"
DEFAULT_URL = "http://127.0.0.1:8501"
REQUIRED_MODULES = ("streamlit", "playwright", "selenium", "requests")


def main() -> int:
    LAUNCHER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT_DIR)

    python_exe = Path(sys.executable)
    if not python_exe.exists():
        print("Python executable could not be found.")
        return 1

    _ensure_python_packages(python_exe)
    _ensure_playwright_browser(python_exe)

    settings = _load_settings()
    _start_ollama_if_needed(settings)
    _maybe_start_brave_attach_target(settings)

    app_url = _ensure_streamlit_running(python_exe)
    _open_dashboard(app_url, settings)

    print(f"JobBot is starting at {app_url}")
    return 0


def _ensure_python_packages(python_exe: Path) -> None:
    missing = [module for module in REQUIRED_MODULES if importlib.util.find_spec(module) is None]
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        _run([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])


def _ensure_playwright_browser(python_exe: Path) -> None:
    playwright_cache = Path.home() / "AppData" / "Local" / "ms-playwright"
    chromium_present = playwright_cache.exists() and any(path.name.startswith("chromium-") for path in playwright_cache.iterdir())
    if not chromium_present:
        print("Installing Playwright Chromium browser...")
        _run([str(python_exe), "-m", "playwright", "install", "chromium"])


def _load_settings() -> dict:
    settings_path = ROOT_DIR / "data" / "config" / "settings.json"
    if not settings_path.exists():
        return {}
    try:
        import json

        return json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _start_ollama_if_needed(settings: dict) -> None:
    ollama_settings = settings.get("ollama", {})
    if not ollama_settings.get("enabled", True):
        return

    base_url = ollama_settings.get("base_url", "http://127.0.0.1:11434").rstrip("/")
    if _http_ok(f"{base_url}/api/tags", timeout=1.5):
        return

    if not _command_exists("ollama"):
        print("Ollama is enabled in settings but was not found in PATH. The UI will still open.")
        return

    print("Starting Ollama in the background...")
    _spawn_background(["ollama", "serve"])
    _wait_for_http(f"{base_url}/api/tags", timeout_seconds=10)


def _maybe_start_brave_attach_target(settings: dict) -> None:
    browser_settings = settings.get("browser", {})
    if not browser_settings.get("attach_to_existing_browser", False):
        return

    debug_url = browser_settings.get("remote_debugging_url", "http://127.0.0.1:9222")
    if _http_ok(f"{debug_url.rstrip('/')}/json/version", timeout=1.5):
        return

    brave_path = browser_settings.get(
        "browser_binary_path",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    )
    if not Path(brave_path).exists():
        print("Attach mode is enabled, but Brave was not found. The UI will still open.")
        return

    parsed = urlparse(debug_url)
    port = parsed.port or 9222
    print("Starting Brave with remote debugging for attach mode...")
    args = [brave_path, f"--remote-debugging-port={port}"]

    user_data_dir = browser_settings.get("browser_user_data_dir", "")
    if user_data_dir:
        args.append(f"--user-data-dir={user_data_dir}")

    _spawn_background(args)
    _wait_for_http(f"{debug_url.rstrip('/')}/json/version", timeout_seconds=12)


def _ensure_streamlit_running(python_exe: Path) -> str:
    if _http_ok(DEFAULT_URL, timeout=1.0):
        return DEFAULT_URL

    print("Starting Streamlit dashboard...")
    with STREAMLIT_LOG_FILE.open("a", encoding="utf-8") as handle:
        _spawn_background(
            [
                str(python_exe),
                "-m",
                "streamlit",
                "run",
                str(STREAMLIT_APP),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            stdout=handle,
            stderr=handle,
        )

    _wait_for_http(DEFAULT_URL, timeout_seconds=20)
    return DEFAULT_URL


def _open_dashboard(app_url: str, settings: dict) -> None:
    browser_settings = settings.get("browser", {})
    brave_path = browser_settings.get("browser_binary_path", "")
    attach_mode = browser_settings.get("attach_to_existing_browser", False)

    if attach_mode and brave_path and Path(brave_path).exists():
        try:
            subprocess.Popen([brave_path, app_url], cwd=str(ROOT_DIR))
            return
        except Exception:  # noqa: BLE001
            pass

    webbrowser.open(app_url)


def _wait_for_http(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _http_ok(url, timeout=1.5):
            return
        time.sleep(0.75)
    print(f"Timed out waiting for {url}. If startup is slow, try opening it manually later.")


def _http_ok(url: str, timeout: float) -> bool:
    try:
        import requests

        response = requests.get(url, timeout=timeout)
        return response.ok
    except Exception:  # noqa: BLE001
        return False


def _command_exists(command: str) -> bool:
    from shutil import which

    return which(command) is not None


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=str(ROOT_DIR), check=True)


def _spawn_background(command: list[str], stdout=None, stderr=None) -> subprocess.Popen:
    creation_flags = 0
    if sys.platform.startswith("win"):
        creation_flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

    return subprocess.Popen(
        command,
        cwd=str(ROOT_DIR),
        stdout=stdout or subprocess.DEVNULL,
        stderr=stderr or subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
        close_fds=False if sys.platform.startswith("win") else True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
