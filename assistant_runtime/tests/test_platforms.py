from __future__ import annotations

import unittest
from unittest.mock import patch

from assistant_runtime.platforms.factory import detect_platform
from assistant_runtime.update_service import UpdateService, version_key


class PlatformTests(unittest.TestCase):
    def test_detects_current_adapter_and_architecture(self) -> None:
        info = detect_platform()
        self.assertTrue(info.system)
        self.assertTrue(info.architecture)
        self.assertTrue(info.adapter.endswith("Adapter"))

    def test_update_asset_matches_supported_windows_architecture(self) -> None:
        with patch("assistant_runtime.update_service.sys.platform", "win32"), patch(
            "assistant_runtime.update_service.platform.machine", return_value="AMD64"
        ):
            self.assertEqual(UpdateService._asset_suffix(), "-win-x64.exe")

    def test_semver_orders_stable_after_prerelease(self) -> None:
        self.assertGreater(version_key("1.0.0"), version_key("1.0.0-beta.1"))
        self.assertGreater(version_key("1.1.0"), version_key("1.0.9"))
