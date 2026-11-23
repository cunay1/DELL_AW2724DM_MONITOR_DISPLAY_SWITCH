from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_installer_rejects_dangerous_install_root_before_sudo(self) -> None:
        environment = dict(os.environ)
        environment["AW2724DM_INSTALL_DIR"] = "/"
        result = subprocess.run(
            [str(ROOT / "install.sh")],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Güvenlik", result.stderr)

    def test_runtime_scripts_do_not_assume_opt_install_path(self) -> None:
        launcher = (ROOT / "packaging" / "aw2724dm-control-launcher").read_text()
        helper = (ROOT / "packaging" / "aw2724dm-update").read_text()
        self.assertNotIn("/opt/aw2724dm-control", launcher)
        self.assertNotIn("/opt/aw2724dm-control", helper)
        self.assertIn("AW2724DM_INSTALL_DIR", helper)


if __name__ == "__main__":
    unittest.main()
