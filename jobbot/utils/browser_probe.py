from __future__ import annotations

import requests


def probe_remote_browser(debug_url: str, timeout_seconds: int = 3) -> tuple[bool, str, dict]:
    try:
        response = requests.get(f"{debug_url.rstrip('/')}/json/version", timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        browser = payload.get("Browser", "Chromium-based browser")
        ws_endpoint = payload.get("webSocketDebuggerUrl", "")
        message = f"Attach target reachable: {browser}"
        if ws_endpoint:
            message += " via CDP."
        return True, message, payload
    except requests.RequestException as exc:
        return False, f"Attach target unavailable at {debug_url}: {exc}", {}
