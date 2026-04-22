import json
import os
import sys
from typing import Any, Dict
from dotenv import load_dotenv

CONFIG_NAME = "config.json"


def app_data_dir() -> str:
    """User-writable directory for runtime data (config, .env, cookies)."""
    path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'VdiskUploader')
    os.makedirs(path, exist_ok=True)
    return path


def project_root() -> str:
    """Directory containing the app binary or source files."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(app_data_dir(), CONFIG_NAME)
    return os.path.join(project_root(), CONFIG_NAME)


def _load_env() -> None:
    if getattr(sys, 'frozen', False):
        load_dotenv(os.path.join(app_data_dir(), '.env'), override=True)
    else:
        load_dotenv(override=True)


def default_config() -> Dict[str, Any]:
    return {
        "upload_method": "browser",
        "endpoint": "https://vdisk.example.com/api/upload",
        "auth_token": "",
        "upload_folder": "/clipboard",
        "watch_text": True,
        "watch_images": True,
        "watch_files": True,
        "poll_interval": 1.0,
        "dry_run": False,
        "enable_upload_prompt": True,
        "browser": {
            "login_url": "https://smartoffice-in.samsung.net/ko-kr/Vdisk",
            "username_selector": "#loginId",
            "password_selector": "#mbrPswd",
            "login_button_selector": "",
            "upload_page_url": "https://smartoffice-in.samsung.net/ko-kr/Vdisk/MyFiles",
            "upload_modal_button_selector": "button[data-ng-click=\"main.vdisk.popup_upload()\"]",
            "file_select_button_selector": "button[data-ng-click=\"main.vdisk.selectFiles();\"]",
            "file_input_selector": "input#files",
            "upload_confirm_button_selector": "button[data-ng-click=\"main.vdisk.uploadFiles()\"]",
            "headless": True,
            "max_wait": 30,
            "reuse_session": True,
        },
    }


def load_config() -> Dict[str, Any]:
    _load_env()
    path = config_path()

    # If running as exe and no user config exists yet, seed from bundled defaults
    if getattr(sys, 'frozen', False) and not os.path.exists(path):
        bundled = os.path.join(project_root(), CONFIG_NAME)
        if os.path.exists(bundled):
            import shutil
            shutil.copy2(bundled, path)

    config = default_config()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            config.update(json.load(handle))

    config["username"] = os.getenv("VDISK_USERNAME", config.get("username", ""))
    config["password"] = os.getenv("VDISK_PASSWORD", config.get("password", ""))
    config["auth_token"] = os.getenv("VDISK_AUTH_TOKEN", config.get("auth_token", ""))

    return config


def save_config(config: Dict[str, Any]) -> None:
    path = config_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
