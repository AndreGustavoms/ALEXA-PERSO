from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from assistant_runtime.settings import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_persists_audio_and_update_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            store.update(
                {
                    "microphone_device": 3,
                    "onboarding_complete": True,
                    "update_channel": "beta",
                }
            )
            loaded = SettingsStore(path).value()
            self.assertEqual(loaded.microphone_device, 3)
            self.assertTrue(loaded.onboarding_complete)
            self.assertEqual(loaded.update_channel, "beta")

    def test_rejects_unknown_or_invalid_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update({"shell": "anything"})
            with self.assertRaises(ValueError):
                store.update({"update_channel": "nightly"})
