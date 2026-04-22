import base64
import subprocess
import sys
from typing import Dict, List, Optional


def _run_powershell(command: str) -> str:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, creationflags=flags,
    )
    return result.stdout.strip()


def read_clipboard() -> Dict[str, object]:
    script = r"""
$result = @{ text = ''; files = ''; image = '' }
$text = Get-Clipboard -Raw -ErrorAction SilentlyContinue
if ($text) { $result.text = $text }
$fileList = Get-Clipboard -Format FileDropList -ErrorAction SilentlyContinue
if ($fileList) { $result.files = $fileList -join [char]0 }
$img = Get-Clipboard -Format Image -ErrorAction SilentlyContinue
if ($img -ne $null) {
    $ms = New-Object System.IO.MemoryStream
    $img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $result.image = [Convert]::ToBase64String($ms.ToArray())
}
"$($result.text)|||$($result.files)|||$($result.image)"
"""
    raw = _run_powershell(script)
    parts = raw.split("|||", 2)
    text_val   = parts[0] if len(parts) > 0 and parts[0] else None
    files_val  = parts[1] if len(parts) > 1 and parts[1] else ""
    image_val  = parts[2] if len(parts) > 2 and parts[2] else ""

    files = [f for f in files_val.split("\0") if f] if files_val else []
    image_bytes: Optional[bytes] = None
    if image_val:
        try:
            image_bytes = base64.b64decode(image_val)
        except ValueError:
            pass

    return {"text": text_val, "files": files, "image_bytes": image_bytes}


def clipboard_signature(state: Dict[str, object]) -> str:
    text = state.get("text") or ""
    files = state.get("files") or []
    image = state.get("image_bytes")
    image_hash = str(len(image)) if image is not None else ""
    return f"text:{text}|files:{','.join(files)}|image:{image_hash}"
