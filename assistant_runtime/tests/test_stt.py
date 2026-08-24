import base64
import json
import os
import unittest
from array import array
from pathlib import Path
from tempfile import TemporaryDirectory

from assistant_runtime.stt import (
    OpenAIRealtimeSTT,
    STTConfig,
    STTEventType,
    load_contextual_vocabulary,
    load_vocabulary,
)
from assistant_runtime.secret_store import load_secret, save_secret


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self.responses: list[str] = []
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def recv(self) -> str:
        if not self.responses:
            raise TimeoutError
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class STTTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "DPAPI existe somente no Windows")
    def test_round_trips_api_key_with_windows_protection(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "key.bin"
            save_secret(path, "sk-test-only")
            self.assertNotIn(b"sk-test-only", path.read_bytes())
            self.assertEqual(load_secret(path), "sk-test-only")

    def test_loads_extensible_vocabulary(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "stt.json"
            (root / "words.txt").write_text(
                "# comentario\nDoktorDev\nVisual Studio Code\n",
                encoding="utf-8",
            )
            config = STTConfig(vocabulary_file="words.txt")
            self.assertEqual(
                load_vocabulary(config_path, config),
                ("DoktorDev", "Visual Studio Code"),
            )

    def test_realtime_session_uses_semantic_vad_and_noise_reduction(self) -> None:
        fake = FakeSocket()
        provider = OpenAIRealtimeSTT(
            STTConfig(
                noise_reduction="far_field",
                semantic_vad_eagerness="low",
            ),
            ("Doktor", "VS Code"),
            api_key="test-key",
            websocket_factory=lambda *args, **kwargs: fake,
        )

        session = provider.start_session(48_000)
        update = fake.sent[0]["session"]  # type: ignore[index]
        audio_input = update["audio"]["input"]  # type: ignore[index]
        self.assertEqual(audio_input["noise_reduction"], {"type": "far_field"})
        self.assertEqual(
            audio_input["turn_detection"],
            {"type": "semantic_vad", "eagerness": "low"},
        )

        session.send_audio(array("h", [10, 20, 30, 40]).tobytes())
        encoded = fake.sent[1]["audio"]
        self.assertEqual(
            array("h", base64.b64decode(str(encoded))).tolist(),
            [10, 30],
        )

        fake.responses.extend(
            [
                json.dumps(
                    {
                        "type": "conversation.item.input_audio_transcription.delta",
                        "delta": "abre o ",
                    }
                ),
                json.dumps(
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "transcript": "abre o YouTube",
                    }
                ),
            ]
        )
        events = session.poll()
        self.assertEqual(
            [event.type for event in events],
            [STTEventType.PARTIAL, STTEventType.COMPLETED],
        )
        self.assertEqual(session.local_result(), "abre o YouTube")

    def test_contextual_vocabulary_adds_visible_apps_without_duplicates(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "stt.json"
            (root / "words.txt").write_text("Spotify\nYouTube\n", encoding="utf-8")
            config = STTConfig(vocabulary_file="words.txt")

            vocabulary = load_contextual_vocabulary(
                config_path,
                config,
                application_discoverer=lambda: ("spotify", "Visual Studio Code"),
            )

        self.assertEqual(vocabulary, ("Spotify", "YouTube", "Visual Studio Code"))


if __name__ == "__main__":
    unittest.main()
