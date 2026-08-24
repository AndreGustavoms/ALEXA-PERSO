from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranscriptionResult:
    provider: str
    text: str
    language: str
    latency_ms: float
    realtime_factor: float


class FasterWhisperSTTProvider:
    """Optional local benchmark provider, intentionally outside app dependencies."""

    def __init__(
        self,
        model_size: str = "base",
        *,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        from faster_whisper import WhisperModel

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=6,
            num_workers=1,
        )

    @property
    def name(self) -> str:
        return f"faster-whisper-{self.model_size}-{self.device}-{self.compute_type}"

    def transcribe(self, path: Path, duration_seconds: float) -> TranscriptionResult:
        started = time.perf_counter()
        segments, info = self._model.transcribe(
            str(path),
            language="pt",
            beam_size=5,
            vad_filter=False,
            condition_on_previous_text=True,
            initial_prompt=(
                "Doktor, DoktorDev, YouTube, Spotify, Discord, Chrome, Edge, "
                "GitHub, Railway, Visual Studio Code, VS Code, React, Next.js, "
                "Node.js, JavaScript, TypeScript, PowerShell, Valorant"
            ),
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        latency_ms = (time.perf_counter() - started) * 1_000
        return TranscriptionResult(
            provider=self.name,
            text=text,
            language=info.language,
            latency_ms=round(latency_ms, 2),
            realtime_factor=round(latency_ms / max(1, duration_seconds * 1_000), 4),
        )
