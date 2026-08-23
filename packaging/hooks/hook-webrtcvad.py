"""webrtcvad-wheels exposes the module as webrtcvad but uses different metadata.

The extension module itself is discovered by PyInstaller; copying metadata from
the abandoned `webrtcvad` distribution would make the upstream hook fail.
"""

datas = []
binaries = []
hiddenimports = []
