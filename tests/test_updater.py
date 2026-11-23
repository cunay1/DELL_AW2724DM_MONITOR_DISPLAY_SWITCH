from __future__ import annotations

import json
import io
import unittest
from unittest.mock import patch

from aw2724dm_control import __version__
from aw2724dm_control.updater import (
    UpdateError,
    UpdateInfo,
    _parse_progress_line,
    apply_update,
    check_for_update,
)


class FakeResponse:
    def __init__(self, version: str, complete: bool = True) -> None:
        names = [
            f"aw2724dm-control-{version}.tar.gz",
            f"aw2724dm-control-{version}.tar.gz.sha256",
            f"aw2724dm-control-{version}.tar.gz.sig",
        ]
        if not complete:
            names.pop()
        self.content = json.dumps(
            {
                "tag_name": f"v{version}",
                "draft": False,
                "prerelease": False,
                "html_url": f"https://example.invalid/releases/v{version}",
                "assets": [{"name": name} for name in names],
            }
        ).encode()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.content[:size]


class UpdaterTests(unittest.TestCase):
    def test_progress_marker_is_parsed_and_localized(self) -> None:
        self.assertEqual(
            _parse_progress_line("AW2724DM_PROGRESS:35:verify"),
            (35, "Verifying the SHA-256 digest and Ed25519 signature…"),
        )
        self.assertIsNone(_parse_progress_line("ordinary installer output"))

    @patch("aw2724dm_control.updater.subprocess.Popen")
    def test_apply_update_reports_live_progress(self, popen) -> None:
        process = popen.return_value
        process.stdout = io.StringIO(
            "AW2724DM_PROGRESS:10:download\n"
            "installer detail that belongs in the log\n"
            "AW2724DM_PROGRESS:65:install\n"
            "AW2724DM_PROGRESS:98:finish\n"
        )
        process.poll.return_value = 0
        process.wait.return_value = 0
        progress: list[tuple[int, str]] = []
        self.assertEqual(apply_update("9.8.7", lambda value, text: progress.append((value, text))), "9.8.7")
        self.assertEqual(progress[0][0], 2)
        self.assertIn((65, "Installing system packages and application files…"), progress)
        self.assertEqual(progress[-1][0], 100)

    @patch("aw2724dm_control.updater.urllib.request.urlopen")
    def test_newer_version_is_reported(self, urlopen) -> None:
        urlopen.return_value = FakeResponse("99.0.0")
        result = check_for_update()
        self.assertIsInstance(result, UpdateInfo)
        self.assertEqual(result.current_version, __version__)
        self.assertEqual(result.available_version, "99.0.0")

    @patch("aw2724dm_control.updater.urllib.request.urlopen")
    def test_current_version_reports_no_update(self, urlopen) -> None:
        urlopen.return_value = FakeResponse(__version__)
        self.assertIsNone(check_for_update())

    @patch("aw2724dm_control.updater.urllib.request.urlopen")
    def test_incomplete_signed_release_is_rejected(self, urlopen) -> None:
        urlopen.return_value = FakeResponse("99.0.0", complete=False)
        with self.assertRaises(UpdateError):
            check_for_update()


if __name__ == "__main__":
    unittest.main()
