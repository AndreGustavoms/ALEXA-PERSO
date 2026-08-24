from __future__ import annotations

import argparse
import json
import queue
import time
from pathlib import Path

import sounddevice as sd
import vosk

from assistant_runtime.app_paths import PATHS
from assistant_runtime.stt import LocalVoskSession
from assistant_runtime.voice_activity import (
    AudioPreprocessor,
    AudioPreRollBuffer,
    TurnManager,
    VoiceActivityConfig,
    VoiceActivityEvent,
    create_speech_detector,
)
from assistant_runtime.wake_word import WakeWordConfig, create_wake_word_engine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor ao vivo do pipeline, sem executar acoes"
    )
    parser.add_argument("--device", type=int)
    args = parser.parse_args()
    voice_config = VoiceActivityConfig.from_file(Path("assistant_runtime/voice_config.json"))
    wake_config = WakeWordConfig.from_file(Path("assistant_runtime/wake_word_config.json"))
    vosk.SetLogLevel(-1)
    model = vosk.Model(str(PATHS.model))
    variants = (wake_config.phrase, "ola doutor")
    grammar = json.dumps([*variants, "[unk]"], ensure_ascii=False)
    frames: queue.Queue[bytes] = queue.Queue(maxsize=voice_config.frames_for(5))
    preprocessor = AudioPreprocessor(voice_config.maximum_input_gain)

    def callback(indata, frame_count, time_info, status) -> None:
        del frame_count, time_info
        if status:
            print(json.dumps({"audio_status": str(status)}))
        try:
            frames.put_nowait(bytes(indata))
        except queue.Full:
            frames.get_nowait()
            frames.put_nowait(bytes(indata))

    def new_wake_engine():
        recognizer = vosk.KaldiRecognizer(model, voice_config.sample_rate, grammar)
        return create_wake_word_engine(
            wake_config,
            recognizer=recognizer,
            variants=variants,
            model_directory=PATHS.voice_models,
        )

    wake = new_wake_engine()
    wake_vad = create_speech_detector(voice_config)
    pre_roll = AudioPreRollBuffer(voice_config)
    turn = None
    stt = None
    state = "WAITING_WAKE"
    turn_started = 0.0
    last_print = 0.0
    last_metrics = None

    print("Voice Lab ativo. Ctrl+C encerra. Nenhuma acao sera executada.")
    try:
        with sd.RawInputStream(
            samplerate=voice_config.sample_rate,
            blocksize=voice_config.frame_samples,
            device=args.device,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while True:
                raw = frames.get()
                processed, last_metrics = preprocessor.process(raw)
                event = VoiceActivityEvent.WAITING
                partial = ""
                wake_score = wake.score
                vad_probability = 0.0
                if stt is None:
                    pre_roll.append(processed)
                    wake_vad.is_speech(processed, voice_config.sample_rate)
                    wake_result = wake.accept(processed, voice_config.sample_rate)
                    wake_score = wake_result.score
                    vad_probability = float(getattr(wake_vad, "score", 0.0))
                    if wake_result.detected:
                        state = "WAKE_DETECTED"
                        turn = TurnManager(voice_config)
                        stt = LocalVoskSession(model, voice_config.sample_rate)
                        turn_started = time.perf_counter()
                        for buffered in pre_roll.snapshot():
                            turn.accept(buffered)
                            stt.send_audio(buffered)
                        pre_roll.clear()
                else:
                    event = turn.accept(processed)
                    stt.send_audio(processed)
                    events = stt.poll()
                    partial = events[-1].text if events else ""
                    vad_probability = turn.vad_probability
                    state = turn.state.value.upper()
                    if event in {VoiceActivityEvent.SPEECH_ENDED, VoiceActivityEvent.START_TIMEOUT}:
                        final = stt.local_result() if turn.has_started else ""
                        print(
                            json.dumps(
                                {
                                    "event": event.value,
                                    "stt_final": final,
                                    "latency_ms": round(
                                        (time.perf_counter() - turn_started) * 1_000, 2
                                    ),
                                    "segment_duration_ms": round(turn.elapsed_seconds * 1_000),
                                    "action_execution": "disabled",
                                },
                                ensure_ascii=False,
                            )
                        )
                        wake = new_wake_engine()
                        wake_vad = create_speech_detector(voice_config)
                        turn = None
                        stt = None
                        state = "WAITING_WAKE"

                now = time.monotonic()
                if now - last_print >= 0.1:
                    print(
                        json.dumps(
                            {
                                "state": state,
                                "raw_rms": round(last_metrics.raw_rms, 5),
                                "raw_peak": round(
                                    AudioPreprocessor._levels(raw)[1], 5
                                ),
                                "processed_rms": round(last_metrics.processed_rms, 5),
                                "processed_peak": round(last_metrics.peak, 5),
                                "noise_floor": round(last_metrics.noise_floor, 5),
                                "gain": round(last_metrics.gain, 2),
                                "clipping": round(last_metrics.clipping, 6),
                                "wake_score": wake_score,
                                "vad_probability": round(vad_probability, 4),
                                "voice_event": event.value,
                                "stt_partial": partial,
                                "action_execution": "disabled",
                            },
                            ensure_ascii=False,
                        )
                    )
                    last_print = now
    except KeyboardInterrupt:
        print("Voice Lab encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
