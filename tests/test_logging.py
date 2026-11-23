from __future__ import annotations

import logging
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from aw2724dm_control.logging_config import (
    LOGGER_NAME,
    export_logs,
    get_logger,
    setup_logging,
)


class LoggingTests(unittest.TestCase):
    def test_logs_are_exported_with_system_information(self) -> None:
        root_logger = logging.getLogger(LOGGER_NAME)
        original_handlers = list(root_logger.handlers)
        root_logger.handlers.clear()
        try:
            with tempfile.TemporaryDirectory() as directory:
                with patch.dict(os.environ, {"XDG_STATE_HOME": directory}):
                    log_path = setup_logging()
                    get_logger("test").error("diagnostic test message")
                    archive_path = export_logs(Path(directory) / "support-bundle.zip")
                    self.assertEqual(log_path.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(archive_path.stat().st_mode & 0o777, 0o600)
                    with zipfile.ZipFile(archive_path) as archive:
                        names = archive.namelist()
                        self.assertIn("system-info.txt", names)
                        self.assertIn("logs/aw2724dm-control.log", names)
                        log_text = archive.read("logs/aw2724dm-control.log").decode()
                        self.assertIn("diagnostic test message", log_text)
        finally:
            for handler in root_logger.handlers:
                handler.close()
            root_logger.handlers[:] = original_handlers
