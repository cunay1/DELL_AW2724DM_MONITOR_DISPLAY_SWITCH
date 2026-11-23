from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from aw2724dm_control import __version__
from aw2724dm_control.updater import UpdateError, UpdateInfo, check_for_update


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
