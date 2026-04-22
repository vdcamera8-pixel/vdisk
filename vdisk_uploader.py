import json
import mimetypes
import os
import urllib.request
from typing import Any, Dict


def _build_headers(config: Dict[str, Any], content_type: str) -> Dict[str, str]:
    headers = {
        "Content-Type": content_type,
    }
    token = config.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _send_request(url: str, data: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"status": "ok", "body": body}


def upload_text(text: str, config: Dict[str, Any]) -> Dict[str, Any]:
    if not config.get("endpoint"):
        raise ValueError("endpoint must be configured")

    payload = {
        "type": "text",
        "upload_folder": config.get("upload_folder"),
        "text": text,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = _build_headers(config, "application/json; charset=utf-8")
    return _send_request(config["endpoint"], body, headers)


def upload_blob(name: str, blob: bytes, content_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    boundary = "----vdisk-upload-boundary"
    lines = []
    lines.append(f"--{boundary}")
    lines.append("Content-Disposition: form-data; name=\"upload_folder\"")
    lines.append("")
    lines.append(config.get("upload_folder", ""))
    lines.append(f"--{boundary}")
    lines.append(f"Content-Disposition: form-data; name=\"file\"; filename=\"{name}\"")
    lines.append(f"Content-Type: {content_type}")
    lines.append("")
    body = "\r\n".join(lines).encode("utf-8") + b"\r\n" + blob + b"\r\n"
    trailer = f"--{boundary}--\r\n".encode("utf-8")
    payload = body + trailer
    headers = _build_headers(config, f"multipart/form-data; boundary={boundary}")
    return _send_request(config["endpoint"], payload, headers)


def upload_image(image_bytes: bytes, config: Dict[str, Any]) -> Dict[str, Any]:
    return upload_blob("clipboard.png", image_bytes, "image/png", config)


def upload_file(path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    name = os.path.basename(path)
    content_type, _ = mimetypes.guess_type(name)
    content_type = content_type or "application/octet-stream"
    with open(path, "rb") as handle:
        data = handle.read()
    return upload_blob(name, data, content_type, config)
