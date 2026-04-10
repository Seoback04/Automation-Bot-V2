from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jobbot.utils.paths import RUNS_DIR, ensure_data_directories


class RunLogger:
    def __init__(self, run_id: str) -> None:
        ensure_data_directories()
        self.run_id = run_id
        self.run_dir = RUNS_DIR / run_id
        self.generated_dir = self.run_dir / "generated"
        self.screenshot_dir = self.run_dir / "screenshots"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.run_dir / "app.log"
        self.events_file = self.run_dir / "events.jsonl"

    def info(self, message: str, **context: Any) -> None:
        self._log("INFO", message, context)

    def warning(self, message: str, **context: Any) -> None:
        self._log("WARNING", message, context)

    def error(self, message: str, **context: Any) -> None:
        self._log("ERROR", message, context)

    def exception(self, message: str, error: Exception) -> None:
        self._log("ERROR", message, {"error": repr(error)})

    def screenshot_path(self, label: str) -> Path:
        safe_label = "".join(char if char.isalnum() or char in "-_" else "_" for char in label).strip("_")
        timestamp = datetime.now().strftime("%H%M%S")
        return self.screenshot_dir / f"{timestamp}_{safe_label or 'capture'}.png"

    def save_snapshot(self, payload: dict[str, Any]) -> None:
        snapshot_path = self.run_dir / "run_snapshot.json"
        snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def save_markdown(self, name: str, content: str) -> Path:
        safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in name).strip("_")
        destination = self.generated_dir / f"{safe_name or 'content'}.md"
        destination.write_text(content, encoding="utf-8")
        return destination

    def _log(self, level: str, message: str, context: dict[str, Any]) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        context_suffix = f" | {json.dumps(context, ensure_ascii=True)}" if context else ""
        line = f"[{timestamp}] {level}: {message}{context_suffix}\n"
        existing = self.log_file.read_text(encoding="utf-8") if self.log_file.exists() else ""
        self.log_file.write_text(existing + line, encoding="utf-8")

        event = {"timestamp": timestamp, "level": level, "message": message, "context": context}
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=True) + "\n")
