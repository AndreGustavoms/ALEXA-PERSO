from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .assistant_commands.entities import EntityResolver
from .assistant_commands.models import WindowContext
from .assistant_commands.parser import IntentParser
from .assistant_commands.router import CommandRouter


@dataclass(frozen=True)
class BenchmarkResult:
    samples: int
    intent_accuracy: float
    entity_accuracy: float
    negative_false_positive_rate: float
    failures: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "intentAccuracy": round(self.intent_accuracy, 4),
            "entityAccuracy": round(self.entity_accuracy, 4),
            "negativeFalsePositiveRate": round(
                self.negative_false_positive_rate, 4
            ),
            "failures": self.failures,
        }


def load_corpus(path: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        payload = json.loads(clean)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise ValueError(f"Registro invalido na linha {line_number}.")
        records.append(payload)
    return tuple(records)


def context_for(name: str) -> WindowContext:
    contexts = {
        "browser_youtube": WindowContext(
            handle=10,
            process_name="chrome.exe",
            title="YouTube - Google Chrome",
            application="Chrome",
            kind="browser",
        ),
        "browser_github": WindowContext(
            handle=11,
            process_name="chrome.exe",
            title="GitHub - Google Chrome",
            application="Chrome",
            kind="browser",
        ),
        "application_spotify": WindowContext(
            handle=20,
            process_name="spotify.exe",
            title="Spotify Premium",
            application="Spotify",
            kind="application",
        ),
        "application_code": WindowContext(
            handle=21,
            process_name="code.exe",
            title="ALEXA-PERSO - Visual Studio Code",
            application="Visual Studio Code",
            kind="application",
        ),
        "none": WindowContext(),
    }
    try:
        return contexts[name]
    except KeyError as error:
        raise ValueError(f"Contexto desconhecido: {name}") from error


def resolved_entity(parameters: dict[str, Any]) -> str:
    raw = str(
        parameters.get("application")
        or parameters.get("target")
        or parameters.get("destination")
        or ""
    )
    if raw.startswith(("http://", "https://")):
        hostname = (urlparse(raw).hostname or "").removeprefix("www.")
        known_hosts = {
            "mail.google.com": "gmail",
            "web.whatsapp.com": "whats app",
        }
        if hostname in known_hosts:
            return known_hosts[hostname]
        return hostname.split(".")[0]
    match = EntityResolver().resolve(raw)
    return match.value if match.confidence else raw


def run_benchmark(path: Path) -> BenchmarkResult:
    records = load_corpus(path)
    router = CommandRouter(IntentParser())
    intent_correct = 0
    entity_correct = 0
    entity_total = 0
    negative_total = 0
    negative_false_positives = 0
    failures: list[dict[str, Any]] = []

    for record in records:
        expected_intent = str(record.get("intent", "NONE"))
        expected_target = str(record.get("target", ""))
        context = context_for(str(record.get("context", "none")))
        previous_target = str(record.get("previousTarget", ""))
        intents = router.parse(record["text"], context, previous_target)
        actual = intents[0] if len(intents) == 1 else None
        actual_intent = actual.kind.value if actual else "NONE"
        actual_target = resolved_entity(actual.parameters) if actual else ""

        intent_matches = actual_intent == expected_intent
        intent_correct += int(intent_matches)
        target_matches = True
        if expected_target:
            entity_total += 1
            target_matches = actual_target == expected_target
            entity_correct += int(target_matches)
        if expected_intent == "NONE":
            negative_total += 1
            negative_false_positives += int(actual is not None)
        if not intent_matches or not target_matches:
            failures.append(
                {
                    "text": record["text"],
                    "expectedIntent": expected_intent,
                    "actualIntent": actual_intent,
                    "expectedTarget": expected_target,
                    "actualTarget": actual_target,
                }
            )

    return BenchmarkResult(
        samples=len(records),
        intent_accuracy=intent_correct / len(records) if records else 0.0,
        entity_accuracy=entity_correct / entity_total if entity_total else 1.0,
        negative_false_positive_rate=(
            negative_false_positives / negative_total if negative_total else 0.0
        ),
        failures=tuple(failures),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de intencoes do Doktor")
    parser.add_argument(
        "corpus",
        nargs="?",
        type=Path,
        default=Path("assistant_runtime/tests/utterances/intent_corpus.jsonl"),
    )
    parser.add_argument("--min-intent", type=float, default=0.97)
    parser.add_argument("--min-entity", type=float, default=0.97)
    parser.add_argument("--max-negative-fp", type=float, default=0.01)
    args = parser.parse_args()
    result = run_benchmark(args.corpus)
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return int(
        result.intent_accuracy < args.min_intent
        or result.entity_accuracy < args.min_entity
        or result.negative_false_positive_rate > args.max_negative_fp
    )


if __name__ == "__main__":
    raise SystemExit(main())
