from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .app_paths import is_frozen
from .version import __version__


DEFAULT_REPOSITORY = "AndreGustavoms/ALEXA-PERSO"
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def version_key(value: str) -> tuple[int, int, int, int, str]:
    match = SEMVER.fullmatch(value)
    if not match:
        raise ValueError(f"Versao invalida: {value}")
    major, minor, patch, suffix = match.groups()
    return int(major), int(minor), int(patch), 1 if suffix is None else 0, suffix or ""


@dataclass(frozen=True)
class UpdateInfo:
    available: bool = False
    currentVersion: str = __version__
    latestVersion: str = __version__
    channel: str = "stable"
    releaseUrl: str = ""
    assetName: str = ""
    downloadUrl: str = ""
    error: str = ""


class UpdateService:
    def __init__(self, channel: str = "stable", repository: str | None = None) -> None:
        self.channel = channel
        self.repository = repository or os.environ.get("DOKTOR_GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
        self.info = UpdateInfo(channel=channel)

    @staticmethod
    def _asset_suffix() -> str:
        machine = platform.machine().lower()
        if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
            return "-win-x64.exe"
        if sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
            return "-linux-x64.AppImage"
        if sys.platform.startswith("linux") and machine in {"aarch64", "arm64"}:
            return "-linux-arm64.AppImage"
        return ""

    def snapshot(self) -> dict[str, Any]:
        return asdict(self.info)

    def check(self) -> UpdateInfo:
        token = os.environ.get("DOKTOR_GITHUB_TOKEN", "").strip()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Doktor/{__version__}",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/releases?per_page=20",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                releases = json.load(response)
            candidates = [release for release in releases if self._allowed(release)]
            release = max(candidates, key=lambda item: version_key(str(item["tag_name"]))) if candidates else None
            if not release:
                self.info = UpdateInfo(channel=self.channel)
                return self.info
            latest = str(release["tag_name"]).removeprefix("v")
            suffix = self._asset_suffix()
            asset = next((item for item in release.get("assets", []) if suffix and str(item.get("name", "")).endswith(suffix)), None)
            available = version_key(latest) > version_key(__version__)
            self.info = UpdateInfo(
                available=available,
                latestVersion=latest,
                channel=self.channel,
                releaseUrl=str(release.get("html_url", "")),
                assetName=str(asset.get("name", "")) if asset else "",
                downloadUrl=str(asset.get("browser_download_url", "")) if asset else "",
                error="" if asset or not available else "Release sem instalador compativel.",
            )
        except Exception as error:
            self.info = UpdateInfo(channel=self.channel, error=str(error))
        return self.info

    def _allowed(self, release: dict[str, Any]) -> bool:
        if release.get("draft") or not SEMVER.fullmatch(str(release.get("tag_name", ""))):
            return False
        prerelease = bool(release.get("prerelease"))
        if self.channel == "stable":
            return not prerelease
        if self.channel == "beta":
            return "dev" not in str(release.get("tag_name", "")).lower()
        return True

    def download_and_install(self) -> Path:
        if not self.info.available or not self.info.downloadUrl:
            raise RuntimeError("Nenhuma atualizacao compativel disponivel.")
        destination = Path(tempfile.gettempdir()) / self.info.assetName
        urllib.request.urlretrieve(self.info.downloadUrl, destination)
        self._verify_checksum(destination)
        if sys.platform == "win32" and is_frozen():
            subprocess.Popen((str(destination), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"))
        else:
            webbrowser.open(self.info.releaseUrl)
        return destination

    def _verify_checksum(self, path: Path) -> None:
        url = self.info.downloadUrl.rsplit("/", 1)[0] + "/SHA256SUMS"
        with urllib.request.urlopen(url, timeout=8) as response:
            checksums = response.read().decode("utf-8")
        expected = next((line.split()[0] for line in checksums.splitlines() if line.split()[-1].lstrip("*") == path.name), "")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not expected or actual.lower() != expected.lower():
            path.unlink(missing_ok=True)
            raise RuntimeError("Checksum da atualizacao invalido.")
