from __future__ import annotations

import logging
import os
import platform
import sys
import zipfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__


LOGGER_NAME = "aw2724dm_control"
LOG_FILE_NAME = "aw2724dm-control.log"
_exception_hook_installed = False


class SecureRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        os.chmod(self.baseFilename, 0o600)
        return stream


def log_directory() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    root = Path(state_home).expanduser() if state_home else Path.home() / ".local" / "state"
    return root / "aw2724dm-control"


def setup_logging() -> Path:
    global _exception_hook_installed
    directory = log_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    path = directory / LOG_FILE_NAME
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        handler = SecureRotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [%(threadName)s] %(message)s",
                "%Y-%m-%dT%H:%M:%S%z",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logging.captureWarnings(True)
    if not _exception_hook_installed:
        previous_hook = sys.excepthook

        def log_uncaught_exception(exception_type, exception, traceback) -> None:
            get_logger("uncaught").critical(
                "Unhandled exception",
                exc_info=(exception_type, exception, traceback),
            )
            previous_hook(exception_type, exception, traceback)

        sys.excepthook = log_uncaught_exception
        _exception_hook_installed = True
    path.touch(mode=0o600, exist_ok=True)
    os.chmod(path, 0o600)
    return path


def get_logger(component: str | None = None) -> logging.Logger:
    name = LOGGER_NAME if not component else f"{LOGGER_NAME}.{component}"
    return logging.getLogger(name)


def _flush_logs() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    for handler in logger.handlers:
        handler.flush()


def export_logs(destination: Path) -> Path:
    setup_logging()
    _flush_logs()
    destination = destination.expanduser()
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    if destination.is_symlink():
        raise OSError("Refusing to overwrite a symbolic link during log export")
    destination.parent.mkdir(parents=True, exist_ok=True)
    directory = log_directory()
    system_info = "\n".join(
        (
            f"AW2724DM Monitor Control: {__version__}",
            f"Python: {platform.python_version()}",
            f"Platform: {platform.platform()}",
            f"Machine: {platform.machine()}",
            f"Session type: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}",
            f"Desktop: {os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}",
            "",
        )
    )
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("system-info.txt", system_info)
        for path in sorted(directory.glob(f"{LOG_FILE_NAME}*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and path.resolve() != destination.resolve()
            ):
                archive.write(path, f"logs/{path.name}")
    os.chmod(destination, 0o600)
    return destination
