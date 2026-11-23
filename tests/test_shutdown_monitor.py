from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from aw2724dm_control.shutdown_monitor import (
    append_abnormal_shutdown_log,
    descendant_process_identities,
    process_matches,
    process_start_time,
)


class ShutdownMonitorTests(unittest.TestCase):
    def test_current_process_identity_is_detected(self) -> None:
        start_time = process_start_time(os.getpid())
        self.assertIsNotNone(start_time)
        self.assertTrue(process_matches(os.getpid(), str(start_time)))
        self.assertFalse(process_matches(os.getpid(), "not-the-start-time"))
        self.assertIsInstance(descendant_process_identities(os.getpid()), list)

    def test_abnormal_shutdown_is_written_to_private_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "application.log"
            append_abnormal_shutdown_log(path, [1234, 5678])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("[1234, 5678] remained alive", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
