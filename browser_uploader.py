import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.sync_api import Page, sync_playwright


def _get_cookies_path(config: Dict[str, Any]) -> str:
    from config import app_data_dir
    return os.path.join(app_data_dir(), "browser_cookies.json")


def _get_system_proxy() -> Optional[str]:
    """Read Windows system proxy settings."""
    try:
        import urllib.request
        proxies = urllib.request.getproxies()
        return proxies.get('https') or proxies.get('http')
    except Exception:
        return None


def _save_debug_screenshot(page, name: str) -> None:
    try:
        from config import app_data_dir
        path = os.path.join(app_data_dir(), f"debug_{name}.png")
        page.screenshot(path=path)
        logging.info("Debug screenshot saved: %s", path)
    except Exception:
        pass


def _launch_browser(playwright, headless: bool = True):
    proxy_server = _get_system_proxy()
    launch_kwargs = {
        "headless": headless,
        "args": ["--ignore-certificate-errors"],
    }
    if proxy_server:
        logging.info("Using system proxy: %s", proxy_server)
        launch_kwargs["proxy"] = {"server": proxy_server}
    return playwright.chromium.launch(**launch_kwargs)


def _new_context(browser):
    return browser.new_context(ignore_https_errors=True)


def _sanitize_filename(filename: str, max_length: int = 50) -> str:
    """Sanitize filename by removing invalid characters and limiting length."""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


def _save_cookies(context, config: Dict[str, Any]) -> None:
    """Save browser cookies to file."""
    cookies_path = _get_cookies_path(config)
    cookies = context.cookies()
    with open(cookies_path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def _load_cookies(context, config: Dict[str, Any]) -> bool:
    """Load browser cookies from file. Returns True if cookies were loaded."""
    cookies_path = _get_cookies_path(config)
    if not os.path.exists(cookies_path):
        return False
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        return True
    except (json.JSONDecodeError, IOError):
        return False


def _browser_config(config: Dict[str, Any]) -> Dict[str, Any]:
    browser_config = config.get("browser", {})
    return {
        "login_url": browser_config.get("login_url", ""),
        "username_selector": browser_config.get("username_selector", ""),
        "password_selector": browser_config.get("password_selector", ""),
        "login_button_selector": browser_config.get("login_button_selector", ""),
        "upload_page_url": browser_config.get("upload_page_url", ""),
        "upload_modal_button_selector": browser_config.get("upload_modal_button_selector", ""),
        "file_select_button_selector": browser_config.get("file_select_button_selector", ""),
        "file_input_selector": browser_config.get("file_input_selector", "input[type=file]"),
        "upload_confirm_button_selector": browser_config.get("upload_confirm_button_selector", ""),
        "headless": browser_config.get("headless", True),
        "max_wait": browser_config.get("max_wait", 30),
        "reuse_session": browser_config.get("reuse_session", True),
    }


def _write_temp_file(suffix: str, data: bytes, filename_hint: str = "") -> str:
    """Write data to temp file with optional filename hint."""
    temp_dir = tempfile.gettempdir()
    if filename_hint:
        # Use hint in filename for better identification
        filename_hint = _sanitize_filename(filename_hint)
        temp_path = os.path.join(temp_dir, f"{filename_hint}_{int(time.time() * 1000)}{suffix}")
        with open(temp_path, 'wb') as f:
            f.write(data)
        return temp_path
    else:
        # Fallback to standard temp file
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp.write(data)
        temp.close()
        return temp.name


def _prepare_text_file(text: str) -> str:
    """Create a text file with content summary in the filename."""
    # Create filename from first 30 chars of text content
    first_line = text.split('\n')[0][:30]
    filename_hint = f"clipboard_text_{_sanitize_filename(first_line)}"
    encoded = text.encode("utf-8")
    path = _write_temp_file(".txt", encoded, filename_hint)
    print(f"Text file created: {path}")
    return path


def _prepare_image_file(image_bytes: bytes) -> str:
    """Create an image file with timestamp in the filename."""
    filename_hint = f"clipboard_image"
    path = _write_temp_file(".png", image_bytes, filename_hint)
    print(f"Image file created: {path}")
    return path


def _click_if_selector(page: Page, selector: str, max_wait: int) -> None:
    if not selector:
        return
    page.wait_for_selector(selector, timeout=max_wait * 1000)
    try:
        page.click(selector)
    except Exception:
        page.eval_on_selector(selector, "el => el.click()")


def _fill_if_selector(page: Page, selector: str, value: str, max_wait: int) -> None:
    if not selector or not value:
        return
    page.wait_for_selector(selector, timeout=max_wait * 1000)
    page.fill(selector, value)


def _login(page: Page, context, config: Dict[str, Any], browser_config: Dict[str, Any]) -> bool:
    """Login to the service. Returns True if login was performed, False if skipped."""
    login_url = browser_config["login_url"]
    if not login_url:
        return False

    print(f"[LOGIN] Attempting to login to {login_url}")
    
    # Try to load existing cookies first
    if browser_config.get("reuse_session", True) and _load_cookies(context, config):
        print("[LOGIN] Loaded cookies from previous session")
        page.goto(login_url)
        page.wait_for_load_state("networkidle")
        if not page.query_selector(browser_config.get("password_selector", "input[type=password]")):
            print("[LOGIN] Already logged in with cookies")
            return False  # Already logged in

    print("[LOGIN] Navigating to login page")
    page.goto(login_url)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)  # Wait for page to fully render
    
    # Close any notification/announcement popups
    print("[LOGIN] Closing notification popups if present")
    # Use only the most specific selectors for Vdisk notice popup
    close_selectors = [
        "#popClose a",  # Vdisk notice popup close button (most specific)
        "#popClose",    # Vdisk notice popup close div
    ]
    for selector in close_selectors:
        try:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"[LOGIN] Found {len(elements)} element(s) with selector: {selector}")
                for element in elements:
                    try:
                        element.click()
                        print(f"[LOGIN] Clicked element with selector: {selector}")
                        page.wait_for_timeout(1000)
                        break
                    except Exception as e:
                        print(f"[LOGIN] Failed to click {selector}: {e}")
                break  # Stop after successfully clicking
        except Exception:
            pass
    
    # Wait for popup to fully close before proceeding
    print("[LOGIN] Waiting for popup to close and login form to appear...")
    page.wait_for_timeout(3000)
    try:
        page.wait_for_selector(browser_config.get("username_selector", "#loginId"), timeout=10000)
        print("[LOGIN] Login form detected after popup close")
    except Exception as e:
        print(f"[LOGIN] Warning: Could not detect login form: {e}")

    username = config.get("username", "")
    password = config.get("password", "")

    if not username or not password:
        raise ValueError("username and password must be configured for login")

    print(f"[LOGIN] Filling username field with selector: {browser_config['username_selector']}")
    _fill_if_selector(page, browser_config["username_selector"], username, browser_config["max_wait"])
    
    print(f"[LOGIN] Filling password field with selector: {browser_config['password_selector']}")
    _fill_if_selector(page, browser_config["password_selector"], password, browser_config["max_wait"])

    if browser_config["login_button_selector"]:
        try:
            print(f"[LOGIN] Clicking login button with selector: {browser_config['login_button_selector']}")
            _click_if_selector(page, browser_config["login_button_selector"], browser_config["max_wait"])
        except Exception:
            print("[LOGIN] Login button click failed, pressing Enter instead")
            page.press(browser_config["password_selector"], "Enter")
    else:
        print("[LOGIN] No login button selector, pressing Enter on password field")
        page.press(browser_config["password_selector"], "Enter")

    print("[LOGIN] Waiting for login to complete")
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    if browser_config.get("reuse_session", True):
        print("[LOGIN] Saving cookies for future sessions")
        _save_cookies(context, config)

    print("[LOGIN] Login completed successfully")
    return True


def _navigate_to_upload(page: Page, browser_config: Dict[str, Any]) -> None:
    upload_page_url = browser_config["upload_page_url"]
    if upload_page_url:
        page.goto(upload_page_url)
        page.wait_for_load_state("networkidle")


def _browser_upload_file(page: Page, path: str, browser_config: Dict[str, Any]) -> None:
    if browser_config["upload_page_url"]:
        page.wait_for_load_state("networkidle")

    if browser_config["upload_modal_button_selector"]:
        try:
            _click_if_selector(page, browser_config["upload_modal_button_selector"], browser_config["max_wait"])
            page.wait_for_timeout(1000)
        except Exception as e:
            print(f"upload_modal_button error: {e}, trying alternative approach")

    if browser_config["file_select_button_selector"]:
        try:
            with page.expect_file_chooser(timeout=10000) as file_chooser_info:
                _click_if_selector(page, browser_config["file_select_button_selector"], browser_config["max_wait"])
            file_chooser = file_chooser_info.value
            file_chooser.set_files(path)
            page.wait_for_timeout(1000)
        except Exception as e:
            print(f"file_select_button error: {e}, trying fallback")
            page.set_input_files(browser_config["file_input_selector"], path)
    else:
        page.set_input_files(browser_config["file_input_selector"], path)

    if browser_config["upload_confirm_button_selector"]:
        try:
            _click_if_selector(page, browser_config["upload_confirm_button_selector"], browser_config["max_wait"])
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            print(f"upload_confirm_button error: {e}")

    # 업로드 완료 검증: 파일 목록에서 새 파일 확인
    try:
        page.goto(browser_config["upload_page_url"], wait_until="networkidle")
        page.wait_for_timeout(2000)  # 파일 목록 로딩 대기
        # 파일 목록에서 업로드된 파일 이름 확인 (임시 파일 이름 기반)
        file_name = os.path.basename(path)
        file_selector = f"//*[contains(text(), '{file_name}')]"
        if page.query_selector(f"xpath={file_selector}"):
            print(f"Upload verification successful: {file_name} found in file list")
            return True
        else:
            print(f"Upload verification failed: {file_name} not found in file list")
            return False
    except Exception as e:
        print(f"Upload verification error: {e}")
        return False


def upload_file_via_browser(path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    browser_config = _browser_config(config)
    with sync_playwright() as playwright:
        browser = _launch_browser(playwright, headless=browser_config["headless"])
        context = _new_context(browser)
        try:
            page = context.new_page()
            _login(page, context, config, browser_config)
            _navigate_to_upload(page, browser_config)
            
            upload_modal_button = page.query_selector(browser_config["upload_modal_button_selector"])
            if upload_modal_button:
                upload_modal_button.evaluate("el => el.click()")
                page.wait_for_timeout(2000)
            
            file_select_button = page.query_selector(browser_config["file_select_button_selector"])
            if file_select_button:
                with page.expect_file_chooser(timeout=15000) as file_chooser_info:
                    file_select_button.click(force=True)
                file_chooser = file_chooser_info.value
                file_chooser.set_files(path)
                page.wait_for_timeout(2000)
            
            upload_confirm = page.query_selector(browser_config["upload_confirm_button_selector"])
            if upload_confirm:
                upload_confirm.click(force=True)
                page.wait_for_timeout(15000)
            
            # 업로드 완료 검증
            verification_success = False
            try:
                page.goto(browser_config["upload_page_url"], wait_until="networkidle")
                page.wait_for_timeout(2000)
                file_name = os.path.basename(path)
                file_selector = f"//*[contains(text(), '{file_name}')]"
                if page.query_selector(f"xpath={file_selector}"):
                    print(f"Upload verification successful: {file_name} found in file list")
                    verification_success = True
                else:
                    print(f"Upload verification failed: {file_name} not found in file list")
            except Exception as e:
                print(f"Upload verification error: {e}")
            
            return {"status": "browser-uploaded", "path": path, "verified": verification_success}
        finally:
            context.close()
            browser.close()


def upload_text_browser(text: str, config: Dict[str, Any]) -> Dict[str, Any]:
    path = _prepare_text_file(text)
    try:
        return upload_file_via_browser(path, config)
    finally:
        # try:
        #     os.remove(path)
        # except OSError:
        #     pass
        print(f"Text file kept for verification: {path}")


def verify_login(username: str, password: str, config: Dict[str, Any]) -> bool:
    """로그인 가능 여부를 확인하고 성공 시 쿠키를 저장합니다."""
    browser_config = _browser_config(config)
    browser = None
    context = None
    try:
        with sync_playwright() as playwright:
            logging.info("[verify_login] Launching browser")
            browser = _launch_browser(playwright, headless=True)
            logging.info("[verify_login] Browser launched")
            context = _new_context(browser)
            logging.info("[verify_login] Context created")
            page = context.new_page()
            login_url = browser_config["login_url"]

            logging.info("[verify_login] Navigating to %s", login_url)
            page.goto(login_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            logging.info("[verify_login] Page loaded. URL: %s", page.url)

            for selector in ["#popClose a", "#popClose"]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click()
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            page.wait_for_timeout(2000)

            username_el = page.query_selector(browser_config["username_selector"])
            password_el = page.query_selector(browser_config["password_selector"])
            logging.info("[verify_login] username field: %s, password field: %s",
                         username_el is not None, password_el is not None)

            if not username_el or not password_el:
                _save_debug_screenshot(page, "login_form_missing")
                logging.error("[verify_login] Login form not found")
                return False

            page.fill(browser_config["username_selector"], username)
            page.fill(browser_config["password_selector"], password)
            page.press(browser_config["password_selector"], "Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            current_url = page.url
            logging.info("[verify_login] After login URL: %s", current_url)

            if login_url in current_url and page.query_selector(browser_config["password_selector"]):
                logging.warning("[verify_login] Still on login page - login failed")
                _save_debug_screenshot(page, "login_failed")
                return False

            logging.info("[verify_login] Login successful")
            _save_cookies(context, config)
            return True
    except Exception as e:
        logging.error("[verify_login] Error: %s", e, exc_info=True)
        return False
    finally:
        try:
            if context:
                context.close()
            if browser:
                browser.close()
        except Exception:
            pass


def upload_image_browser(image_bytes: bytes, config: Dict[str, Any]) -> Dict[str, Any]:
    path = _prepare_image_file(image_bytes)
    try:
        return upload_file_via_browser(path, config)
    finally:
        # try:
        #     os.remove(path)
        # except OSError:
        #     pass
        print(f"Image file kept for verification: {path}")
