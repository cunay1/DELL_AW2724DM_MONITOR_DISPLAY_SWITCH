from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from . import __version__
from .i18n import tr
from .logging_config import get_logger


REPOSITORY = "cunay1/DELL_AW2724DM_MONITOR_DISPLAY_SWITCH"
RELEASE_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPOSITORY}/releases"
UPDATE_HELPER = "/opt/aw2724dm-control/aw2724dm-update"
PROGRESS_PREFIX = "AW2724DM_PROGRESS:"
logger = get_logger("updater")


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
        raise UpdateError(tr("invalid_release_version", version=value))
    return tuple(int(part) for part in parts)


def check_for_update() -> UpdateInfo | None:
    logger.info("Checking GitHub Releases for updates")
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
        raise UpdateError(tr("release_http_error", code=exc.code)) from exc
    except json.JSONDecodeError as exc:
        raise UpdateError(tr("release_invalid_json")) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(tr("release_access_error", error=exc)) from exc
    tag = str(payload.get("tag_name", ""))
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag)
    if not match or payload.get("draft") or payload.get("prerelease"):
        raise UpdateError(tr("release_invalid"))
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
        raise UpdateError(tr("release_assets_missing"))
    if _version_key(available) > _version_key(__version__):
        logger.info("Update available: %s -> %s", __version__, available)
        return UpdateInfo(__version__, available, str(payload.get("html_url", RELEASE_PAGE)))
    logger.info("No update available; current=%s latest=%s", __version__, available)
    return None


def _parse_progress_line(line: str) -> tuple[int, str] | None:
    if not line.startswith(PROGRESS_PREFIX):
        return None
    parts = line.strip().split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    value = max(0, min(100, int(parts[1])))
    stage_keys = {
        "download": "update_stage_download",
        "verify": "update_stage_verify",
        "extract": "update_stage_extract",
        "install": "update_stage_install",
        "finish": "update_stage_finish",
    }
    message_key = stage_keys.get(parts[2])
    return (value, tr(message_key)) if message_key else None


def apply_update(
    version: str,
    progress_callback: Callable[[int, str], None] | None = None,
) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise UpdateError(tr("invalid_update_version", version=version))
    progress = progress_callback or (lambda _value, _message: None)
    progress(2, tr("update_stage_authorize"))
    logger.info("Starting signed update to version %s", version)
    try:
        process = subprocess.Popen(
            ["pkexec", UPDATE_HELPER, version],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        logger.exception("Update helper could not be started")
        raise UpdateError(tr("update_helper_failed", error=exc)) from exc

    output: queue.Queue[str | None] = queue.Queue(maxsize=1000)

    def read_output() -> None:
        assert process.stdout is not None
        for raw_line in process.stdout:
            output.put(raw_line.rstrip("\r\n"))
        output.put(None)

    threading.Thread(target=read_output, name="update-output", daemon=True).start()
    deadline = time.monotonic() + 300
    reader_finished = False
    last_output = ""
    while process.poll() is None or not reader_finished:
        if time.monotonic() >= deadline:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.error("Update helper timed out")
            raise UpdateError(tr("update_timeout"))
        try:
            line = output.get(timeout=0.2)
        except queue.Empty:
            continue
        if line is None:
            reader_finished = True
            continue
        parsed = _parse_progress_line(line)
        if parsed:
            logger.info("Update progress %s%%: %s", parsed[0], parsed[1])
            progress(*parsed)
        elif line:
            last_output = line[-500:]
            logger.debug("Update helper: %s", line)

    return_code = process.wait()
    if return_code != 0:
        logger.error("Update helper exited with code %s; last output: %s", return_code, last_output)
        if return_code in (126, 127):
            raise UpdateError(tr("authorization_cancelled"))
        raise UpdateError(tr("update_failed_log", code=return_code))
    progress(100, tr("update_stage_finish"))
    logger.info("Signed update to version %s completed", version)
    return version
