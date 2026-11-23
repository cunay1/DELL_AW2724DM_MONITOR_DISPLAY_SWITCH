from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "selected_display": 1,
    "aliases": {},
    "toggle_inputs": {},
    "close_to_tray": True,
    "check_updates": True,
    "last_update_check": 0,
}


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".config" / "aw2724dm-control" / "config.json"
        self._lock = RLock()
        self.data = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._normalize()
                return
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (OSError, json.JSONDecodeError):
                # Bozuk dosyayı ezmeden güvenli varsayılanlarla devam edilir.
                self._normalize()
                return
            self._normalize()

    def _normalize(self) -> None:
        try:
            selected = int(self.data.get("selected_display", 1))
        except (TypeError, ValueError):
            selected = 1
        self.data["selected_display"] = max(1, selected)
        if not isinstance(self.data.get("aliases"), dict):
            self.data["aliases"] = {}
        if not isinstance(self.data.get("toggle_inputs"), dict):
            self.data["toggle_inputs"] = {}
        self.data["close_to_tray"] = bool(self.data.get("close_to_tray", True))
        self.data["check_updates"] = bool(self.data.get("check_updates", True))
        try:
            self.data["last_update_check"] = max(0, int(self.data.get("last_update_check", 0)))
        except (TypeError, ValueError):
            self.data["last_update_check"] = 0

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix="config-", suffix=".json", dir=self.path.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self.data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
                os.chmod(self.path, 0o600)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def display_key(self, display: int) -> str:
        return str(display)

    def aliases(self, display: int) -> dict[str, str]:
        root = self.data.setdefault("aliases", {})
        values = root.get(self.display_key(display))
        if not isinstance(values, dict):
            values = {}
            root[self.display_key(display)] = values
        return values

    def set_alias(self, display: int, code: int, alias: str) -> None:
        key = f"0x{code:02x}"
        aliases = self.aliases(display)
        if alias.strip():
            aliases[key] = alias.strip()
        else:
            aliases.pop(key, None)
        self.save()

    def toggle_inputs(self, display: int) -> tuple[int, int] | None:
        raw = self.data.setdefault("toggle_inputs", {}).get(self.display_key(display))
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        try:
            return int(str(raw[0]), 0), int(str(raw[1]), 0)
        except ValueError:
            return None

    def set_toggle_inputs(self, display: int, first: int, second: int) -> None:
        root = self.data.setdefault("toggle_inputs", {})
        if not isinstance(root, dict):
            root = {}
            self.data["toggle_inputs"] = root
        root[self.display_key(display)] = [
            f"0x{first:02x}",
            f"0x{second:02x}",
        ]
        self.save()
