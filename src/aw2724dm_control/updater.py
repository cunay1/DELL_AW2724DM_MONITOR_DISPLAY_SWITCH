from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import __version__


REPOSITORY = "cunay1/DELL_AW2724DM_MONITOR_DISPLAY_SWITCH"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPOSITORY}/releases"
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
        RELEASE_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"aw2724dm-control/{__version__}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read(1024 * 1024).decode("utf-8", errors="replace")
            payload = json.loads(content)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise UpdateError(f"GitHub Release bilgisine ulaşılamadı: HTTP {exc.code}") from exc
    except json.JSONDecodeError as exc:
        raise UpdateError("GitHub Release yanıtı geçerli JSON değil.") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"GitHub Release bilgisine ulaşılamadı: {exc}") from exc
    tag = str(payload.get("tag_name", ""))
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
    if not match or payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("GitHub üzerindeki kararlı sürüm bilgisi geçersiz.")
    available = match.group(1)
    expected_assets = {
        f"aw2724dm-control-{available}.tar.gz",
        f"aw2724dm-control-{available}.tar.gz.sha256",
        f"aw2724dm-control-{available}.tar.gz.sig",
    }
    assets = {
        str(asset.get("name", ""))
        for asset in payload.get("assets", [])
        if isinstance(asset, dict)
    }
    if not expected_assets.issubset(assets):
        raise UpdateError("Release, gerekli imzalı güncelleme dosyalarının tümünü içermiyor.")
    if _version_key(available) > _version_key(__version__):
        return UpdateInfo(__version__, available, str(payload.get("html_url", RELEASE_PAGE)))
    return None


def apply_update(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise UpdateError(f"Geçersiz güncelleme sürümü: {version}")
    try:
        result = subprocess.run(
            ["pkexec", UPDATE_HELPER, version],
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
