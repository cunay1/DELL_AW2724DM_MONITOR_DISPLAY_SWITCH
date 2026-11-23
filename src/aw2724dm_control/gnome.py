from __future__ import annotations

import ast
import re
import subprocess


class GSettingsError(RuntimeError):
    """GNOME gsettings okuma veya yazma hatası."""


SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KEY = "custom-keybindings"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"


def _run(*args: str) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GSettingsError(f"gsettings çalıştırılamadı: {exc}") from exc
    if result.returncode != 0:
        raise GSettingsError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def install_shortcut(name: str, command: str, binding: str) -> str:
    current_text = _run("gsettings", "get", SCHEMA, KEY)
    try:
        current = ast.literal_eval(current_text.replace("@as ", ""))
    except (ValueError, SyntaxError) as exc:
        raise GSettingsError("Mevcut GNOME kısayol listesi okunamadı.") from exc
    if not isinstance(current, list):
        current = []
    used = {int(match.group(1)) for path in current if (match := re.search(r"custom(\d+)/$", path))}
    index = next(number for number in range(1000) if number not in used)
    path = f"{BASE}/custom{index}/"
    schema_path = f"{SCHEMA}.custom-keybinding:{path}"
    _run("gsettings", "set", schema_path, "name", name)
    _run("gsettings", "set", schema_path, "command", command)
    _run("gsettings", "set", schema_path, "binding", binding)
    current.append(path)
    formatted = "[" + ", ".join(repr(item) for item in current) + "]"
    _run("gsettings", "set", SCHEMA, KEY, formatted)
    return path
