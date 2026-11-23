from __future__ import annotations

import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import __version__


VERSION_URL = (
    "https://raw.githubusercontent.com/cunay1/"
    "DELL_AW2724DM_MONITOR_DISPLAY_SWITCH/main/src/aw2724dm_control/__init__.py"
)
RELEASE_PAGE = "https://github.com/cunay1/DELL_AW2724DM_MONITOR_DISPLAY_SWITCH"
UPDATE_HELPER = "/opt/aw2724dm-control/aw2724dm-update"


class UpdateError(RuntimeError):
    """Güncelleme denetleme veya uygulama hatası."""


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current_version: str
    available_version: str
    page_url: str = RELEASE_PAGE


def _version_key(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    if not parts:
        raise UpdateError(f"Geçersiz sürüm numarası: {value}")
    return tuple(int(part) for part in parts)


def check_for_update() -> UpdateInfo | None:
    request = urllib.request.Request(
        VERSION_URL,
        headers={"User-Agent": f"aw2724dm-control/{__version__}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read(64 * 1024).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"GitHub sürüm bilgisine ulaşılamadı: {exc}") from exc
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise UpdateError("GitHub üzerindeki sürüm bilgisi çözümlenemedi.")
    available = match.group(1)
    if _version_key(available) > _version_key(__version__):
        return UpdateInfo(__version__, available)
    return None


def apply_update() -> str:
    try:
        result = subprocess.run(
            ["pkexec", UPDATE_HELPER],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateError("Güncelleme işlemi beş dakika içinde tamamlanamadı.") from exc
    except OSError as exc:
        raise UpdateError(f"Güncelleme yardımcısı çalıştırılamadı: {exc}") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        if result.returncode in (126, 127):
            message = "Yönetici yetkilendirmesi iptal edildi veya pkexec çalıştırılamadı."
        raise UpdateError(message or f"Güncelleme {result.returncode} koduyla sonlandı.")
    return result.stdout.strip()
