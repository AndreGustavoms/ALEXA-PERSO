#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '\r\n' < "$ROOT/VERSION")"
MACHINE="$(uname -m)"
case "$MACHINE" in
  x86_64) APP_ARCH="x64"; DEB_ARCH="amd64"; TOOL_ARCH="x86_64" ;;
  aarch64|arm64) APP_ARCH="arm64"; DEB_ARCH="arm64"; TOOL_ARCH="aarch64" ;;
  *) echo "Arquitetura Linux sem pacote: $MACHINE" >&2; exit 2 ;;
esac

OUT="$ROOT/build/installers"
APPDIR="$ROOT/build/Doktor.AppDir"
DEBROOT="$ROOT/build/deb-root"
rm -rf "$APPDIR" "$DEBROOT"
mkdir -p "$OUT" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/build/pyinstaller/Doktor/." "$APPDIR/usr/bin/"
cp "$ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"
cp "$ROOT/packaging/linux/doktor-assistant.desktop" "$APPDIR/doktor-assistant.desktop"
cp "$ROOT/packaging/linux/doktor-assistant.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/assets/doktor-assistant.png" "$APPDIR/doktor-assistant.png"
cp "$ROOT/assets/doktor-assistant.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/doktor-assistant.png"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/Doktor"

APPIMAGE_TOOL="$ROOT/build/appimagetool-${TOOL_ARCH}.AppImage"
if [[ ! -x "$APPIMAGE_TOOL" ]]; then
  curl --fail --location --retry 3 "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${TOOL_ARCH}.AppImage" -o "$APPIMAGE_TOOL"
  chmod +x "$APPIMAGE_TOOL"
fi
ARCH="$TOOL_ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE_TOOL" "$APPDIR" "$OUT/Doktor-${VERSION}-linux-${APP_ARCH}.AppImage"

mkdir -p "$DEBROOT/DEBIAN" "$DEBROOT/opt/doktor-assistant" "$DEBROOT/usr/bin" "$DEBROOT/usr/share/applications" "$DEBROOT/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/build/pyinstaller/Doktor/." "$DEBROOT/opt/doktor-assistant/"
ln -s /opt/doktor-assistant/Doktor "$DEBROOT/usr/bin/doktor-assistant"
sed 's/^Exec=.*/Exec=doktor-assistant --open/' "$ROOT/packaging/linux/doktor-assistant.desktop" > "$DEBROOT/usr/share/applications/doktor-assistant.desktop"
cp "$ROOT/assets/doktor-assistant.png" "$DEBROOT/usr/share/icons/hicolor/256x256/apps/doktor-assistant.png"
cat > "$DEBROOT/DEBIAN/control" <<EOF
Package: doktor-assistant
Version: $VERSION
Section: utils
Priority: optional
Architecture: $DEB_ARCH
Maintainer: AndreGustavoms
Description: Assistente de voz local Doktor
EOF
dpkg-deb --build --root-owner-group "$DEBROOT" "$OUT/Doktor-${VERSION}-linux-${DEB_ARCH}.deb"
