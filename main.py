import os
import sys

# Must be set before any playwright import when running as a frozen exe
if getattr(sys, 'frozen', False):
    _browsers_path = os.path.join(os.path.dirname(sys.executable), 'playwright_browsers')
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', _browsers_path)

import argparse
import base64
import ctypes
import json
import logging
import threading
import time
from typing import Dict, Optional

from browser_uploader import upload_file_via_browser, upload_image_browser, upload_text_browser
from clipboard import clipboard_signature, read_clipboard
from config import load_config, save_config
from gui_notification import show_upload_prompt, show_upload_complete
from vdisk_uploader import upload_file, upload_image, upload_text


def _setup_logging() -> None:
    from config import app_data_dir
    log_path = os.path.join(app_data_dir(), "vdisk_uploader.log")
    handlers = [logging.FileHandler(log_path, encoding="utf-8")]
    if not getattr(sys, 'frozen', False):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s %(message)s",
                        handlers=handlers)

_setup_logging()

_MUTEX_NAME = "VdiskUploaderSingleInstance"


def ensure_single_instance() -> bool:
    """Returns False if another instance is already running."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != 183  # 183 = ERROR_ALREADY_EXISTS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vdisk clipboard auto-uploader")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Create or update config.json")
    init_parser.add_argument("--endpoint", help="VDisk upload endpoint URL")
    init_parser.add_argument("--token", help="Authentication token")
    init_parser.add_argument("--upload-folder", help="Remote folder path")
    init_parser.add_argument("--upload-method", choices=["api", "browser"], help="Upload method to use")
    init_parser.add_argument("--poll-interval", type=float, help="Clipboard polling interval in seconds")
    init_parser.add_argument("--dry-run", action="store_true", help="Do not perform actual upload")

    run_parser = subparsers.add_parser("run", help="Start clipboard watcher")
    run_parser.add_argument("--dry-run", action="store_true", help="Do not perform actual upload")
    run_parser.add_argument("--interval", type=float, help="Polling interval in seconds")

    subparsers.add_parser("status", help="Show current config and watcher status")

    upload_text_parser = subparsers.add_parser("upload-text", help="Upload text immediately")
    upload_text_parser.add_argument("--text", required=True, help="Text to upload")

    simulate_parser = subparsers.add_parser("simulate", help="Simulate clipboard uploads for text, image, and file")
    simulate_parser.add_argument("--dry-run", action="store_true", help="Do not perform actual upload")

    return parser.parse_args()


def init_config(args: argparse.Namespace, config: Dict[str, object]) -> None:
    if args.endpoint:
        config["endpoint"] = args.endpoint
    if args.token:
        config["auth_token"] = args.token
    if args.upload_folder:
        config["upload_folder"] = args.upload_folder
    if args.upload_method:
        config["upload_method"] = args.upload_method
    if args.poll_interval is not None:
        config["poll_interval"] = args.poll_interval
    if args.dry_run:
        config["dry_run"] = True
    save_config(config)
    logging.info("Saved config to config.json")


def show_status(config: Dict[str, object]) -> None:
    logging.info("Current configuration:")
    print(json.dumps(config, indent=2, ensure_ascii=False))


def safe_upload_text(text: str, config: Dict[str, object]) -> None:
    if config.get("dry_run"):
        logging.info("[DRY-RUN] Would upload text: %s", text[:80])
        show_upload_complete("텍스트", success=True)
        return
    try:
        if config.get("upload_method", "browser") == "browser":
            response = upload_text_browser(text, config)
        else:
            response = upload_text(text, config)
        verified = response.get("verified", False)
        logging.info("Upload text response: %s (verified: %s)", response, verified)
        show_upload_complete("텍스트", success=True)
    except Exception as exc:
        logging.error("Upload text failed: %s", exc)
        show_upload_complete("텍스트", success=False)


def safe_upload_image(image_bytes: bytes, config: Dict[str, object]) -> None:
    if config.get("dry_run"):
        logging.info("[DRY-RUN] Would upload image (%d bytes)", len(image_bytes))
        show_upload_complete("이미지", success=True)
        return
    try:
        if config.get("upload_method", "browser") == "browser":
            response = upload_image_browser(image_bytes, config)
        else:
            response = upload_image(image_bytes, config)
        logging.info("Upload image response: %s", response)
        show_upload_complete("이미지", success=True)
    except Exception as exc:
        logging.error("Upload image failed: %s", exc)
        show_upload_complete("이미지", success=False)


def safe_upload_file(path: str, config: Dict[str, object]) -> None:
    if config.get("dry_run"):
        logging.info("[DRY-RUN] Would upload file: %s", path)
        show_upload_complete("파일", success=True)
        return
    try:
        if config.get("upload_method", "browser") == "browser":
            response = upload_file_via_browser(path, config)
        else:
            response = upload_file(path, config)
        logging.info("Upload file response: %s", response)
        show_upload_complete("파일", success=True)
    except Exception as exc:
        logging.error("Upload file failed: %s", exc)
        show_upload_complete("파일", success=False)


def simulate_uploads(config: Dict[str, object]) -> None:
    logging.info("Running simulated clipboard uploads")
    config = config.copy()
    config["dry_run"] = True

    sample_text = "[SIMULATION] Clipboard text upload test"
    sample_image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAn8B9fG/lAAAAABJRU5ErkJggg=="
    )

    safe_upload_text(sample_text, config)
    safe_upload_image(sample_image_bytes, config)

    temp_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation-test.txt")
    with open(temp_file_path, "w", encoding="utf-8") as f:
        f.write("[SIMULATION] Clipboard file upload test")
    try:
        safe_upload_file(temp_file_path, config)
    finally:
        try:
            os.remove(temp_file_path)
        except OSError:
            pass


def watch_clipboard(config: Dict[str, object], interval: float,
                    stop_event: threading.Event = None) -> None:
    logging.info("Starting clipboard watcher with interval %s seconds", interval)
    enable_prompt = config.get("enable_upload_prompt", True)

    last_signature = ""
    while not (stop_event and stop_event.is_set()):
        try:
            state = read_clipboard()
            signature = clipboard_signature(state)
            if signature != last_signature:
                logging.info("Clipboard changed")
                logging.info("Text: %s, Image: %s, Files: %s", bool(state["text"]), bool(state["image_bytes"]), state["files"])
                last_signature = signature

                if state["text"] and config.get("watch_text", True):
                    text_preview = state["text"][:50]
                    if enable_prompt:
                        if show_upload_prompt(text_preview, "텍스트", timeout=10):
                            safe_upload_text(state["text"], config)
                        else:
                            logging.info("Text upload skipped by user")
                    else:
                        safe_upload_text(state["text"], config)

                if state["image_bytes"] and config.get("watch_images", True):
                    image_size = len(state["image_bytes"]) / 1024
                    image_preview = f"Image ({image_size:.1f} KB)"
                    if enable_prompt:
                        if show_upload_prompt(image_preview, "이미지", timeout=10):
                            safe_upload_image(state["image_bytes"], config)
                        else:
                            logging.info("Image upload skipped by user")
                    else:
                        safe_upload_image(state["image_bytes"], config)

                for path in state["files"]:
                    if config.get("watch_files", True) and os.path.exists(path):
                        file_name = os.path.basename(path)
                        if enable_prompt:
                            if show_upload_prompt(file_name, "파일", timeout=10):
                                safe_upload_file(path, config)
                            else:
                                logging.info("File upload '%s' skipped by user", file_name)
                        else:
                            safe_upload_file(path, config)

            time.sleep(interval)
        except KeyboardInterrupt:
            logging.info("Stopped by user")
            return
        except Exception as exc:
            logging.error("Watcher error: %s", exc)
            time.sleep(interval)


def run_with_tray(config: Dict[str, object]) -> None:
    from system_tray import run_tray

    stop_event = threading.Event()

    def on_quit():
        logging.info("Quit requested from tray")

    tray_thread = threading.Thread(
        target=run_tray,
        args=(stop_event, on_quit),
        daemon=True,
    )
    tray_thread.start()

    interval = float(config.get("poll_interval", 1.0))
    watch_clipboard(config, interval, stop_event)


def main() -> None:
    args = parse_args()

    if args.command in (None, "run"):
        if not ensure_single_instance():
            logging.warning("Vdisk Uploader is already running.")
            sys.exit(0)

        from config import app_data_dir
        env_path = os.path.join(app_data_dir(), ".env")
        from setup_wizard import run_setup_if_needed
        if not run_setup_if_needed(env_path):
            logging.error("Setup was not completed. Exiting.")
            return

    config = load_config()
    if args.command == "init":
        init_config(args, config)
        return
    if args.command == "status":
        show_status(config)
        return
    if args.command == "upload-text":
        safe_upload_text(args.text, config)
        return
    if args.command == "simulate":
        if args.dry_run:
            config["dry_run"] = True
        simulate_uploads(config)
        return
    if args.command == "run":
        if args.interval is not None:
            config["poll_interval"] = args.interval
        if args.dry_run:
            config["dry_run"] = True
        run_with_tray(config)
        return

    logging.error("No command specified. Use --help for usage.")


if __name__ == "__main__":
    main()
