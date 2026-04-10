from __future__ import annotations

import json

from jobbot.automation.controller import AutomationController
from jobbot.config.manager import ConfigManager


def main() -> None:
    manager = ConfigManager()
    controller = AutomationController(manager)
    snapshot = controller.start()
    print(json.dumps(snapshot, indent=2))

    while snapshot.get("pending_checkpoint"):
        input(f"\n{snapshot['pending_checkpoint']['message']}\nPress Enter to continue...")
        snapshot = controller.resume()
        print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
