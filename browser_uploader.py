import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from playwright.sync_api import BrowserContext, Page, sync_playwright


def _get_cookies_path(config: Dict[str, Any]) -> str:
    from config import app_data_dir
    return os.path.join(app_data_dir(), "browser_cookies.json")


def _get_system_proxy() -> Tuple[Optional[str], Optional[str]]:
    """Return (proxy_server, bypass_list) from system proxy settings.
    Samsung intranet domains (.samsung.net) are always in the bypass list so
    that Kerberos/NTLM authentication can work directly with the server.
    Without bypass, Playwright routes Samsung traffic through the proxy and
    Windows integrated auth is broken — the server falls back to 'PC(사내)'."""
    try:
        import urllib.request
        proxies = urllib.request.getproxies()
        server = proxies.get('https') or proxies.get('http')
        # urllib uses 'no' key for no_proxy; merge with our Samsung-specific bypass
        no_proxy = proxies.get('no', '')
        samsung_bypass = '.samsung.net,.samsung.com'
        bypass = f"{no_proxy},{samsung_bypass}" if no_proxy else samsung_bypass
        return server, bypass
    except Exception:
        return None, None


def _save_debug_screenshot(page, name: str) -> None:
    try:
        from config import app_data_dir
        path = os.path.join(app_data_dir(), f"debug_{name}.png")
        page.screenshot(path=path)
        logging.info("Debug screenshot saved: %s", path)
    except Exception:
        pass


def _get_chrome_user_data_dir() -> Optional[str]:
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    path = os.path.join(local_app_data, 'Google', 'Chrome', 'User Data')
    return path if os.path.exists(path) else None


_CHROME_SKIP_DIRS = {
    'GPUCache', 'Cache', 'Code Cache', 'CacheStorage',
    'Service Worker', 'DawnCache', 'ShaderCache', 'Sessions',
}


def _copy_chrome_profile(user_data_dir: str) -> Optional[str]:
    """Copy Chrome Default profile to a temp dir, skipping locked/cache files.
    Individual locked files (e.g. Cookies when Chrome is running) are silently
    skipped — the copy continues so that Extensions and other key dirs land.
    Returns the temp dir path, or None if the Extensions dir could not be copied."""
    temp_dir = tempfile.mkdtemp(prefix='vdisk_chrome_')
    src_default = os.path.join(user_data_dir, 'Default')
    dst_default = os.path.join(temp_dir, 'Default')

    copied = 0
    skipped = 0
    for root, dirs, files in os.walk(src_default):
        dirs[:] = [d for d in dirs if d not in _CHROME_SKIP_DIRS]
        rel = os.path.relpath(root, src_default)
        dst_root = os.path.join(dst_default, rel) if rel != '.' else dst_default
        os.makedirs(dst_root, exist_ok=True)
        for fname in files:
            try:
                shutil.copy2(os.path.join(root, fname), os.path.join(dst_root, fname))
                copied += 1
            except (OSError, IOError):
                skipped += 1  # file locked by Chrome — skip it

    # Local State holds the AES key needed to decrypt Chrome cookies
    try:
        shutil.copy2(os.path.join(user_data_dir, 'Local State'),
                     os.path.join(temp_dir, 'Local State'))
    except (OSError, IOError):
        pass

    ext_dir = os.path.join(dst_default, 'Extensions')
    if not os.path.isdir(ext_dir):
        logging.warning("Chrome Extensions dir missing after copy — aborting profile launch")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None

    logging.info("Chrome profile copied: %d files, %d skipped (locked)", copied, skipped)
    return temp_dir


def _launch_with_chrome_profile(playwright, temp_profile_dir: str,
                                  headless: bool = True) -> Optional[BrowserContext]:
    """Launch Chrome with the copied user profile via launch_persistent_context.
    Samsung intranet domains bypass the proxy so Windows Kerberos/NTLM auth
    works directly — that is how the server resolves the device name to
    'SEC-AI-D-03354(사내)' instead of the generic 'PC(사내)'."""
    proxy_server, bypass = _get_system_proxy()
    launch_kwargs: Dict[str, Any] = {
        'channel': 'chrome',
        'headless': headless,
        'args': [
            '--ignore-certificate-errors',
            '--no-first-run',
            '--no-default-browser-check',
            # Allow automatic Windows Kerberos/NTLM auth for Samsung domains
            '--auth-server-allowlist=*.samsung.net,*.samsung.com',
            '--auth-negotiate-delegate-allowlist=*.samsung.net,*.samsung.com',
            # Suppress the automation banner so security extensions (NASCA) behave normally
            '--disable-blink-features=AutomationControlled',
        ],
        'ignore_https_errors': True,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/147.0.0.0 Safari/537.36'
        ),
    }
    if proxy_server:
        logging.info("Chrome profile launch: proxy=%s bypass=%s", proxy_server, bypass)
        launch_kwargs['proxy'] = {'server': proxy_server, 'bypass': bypass or ''}
    try:
        ctx = playwright.chromium.launch_persistent_context(temp_profile_dir, **launch_kwargs)
        logging.info("Launched Chrome with user profile (device identity preserved)")
        return ctx
    except Exception as e:
        logging.warning("Chrome profile launch failed: %s", e)
        return None


def _launch_browser(playwright, headless: bool = True):
    proxy_server, bypass = _get_system_proxy()
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--ignore-certificate-errors",
            "--auth-server-allowlist=*.samsung.net,*.samsung.com",
            "--auth-negotiate-delegate-allowlist=*.samsung.net,*.samsung.com",
            "--disable-blink-features=AutomationControlled",
        ],
    }
    if proxy_server:
        logging.info("Using system proxy: %s (bypass: %s)", proxy_server, bypass)
        launch_kwargs["proxy"] = {"server": proxy_server, "bypass": bypass or ""}

    try:
        browser = playwright.chromium.launch(channel="chrome", **launch_kwargs)
        logging.info("Using system Chrome")
        return browser
    except Exception as e:
        logging.warning("System Chrome not available (%s), falling back to bundled Chromium", e)
        return playwright.chromium.launch(**launch_kwargs)


_CHROME_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/147.0.0.0 Safari/537.36'
)


def _new_context(browser):
    return browser.new_context(
        ignore_https_errors=True,
        user_agent=_CHROME_UA,
    )


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


_NASCA_EXT_ID = 'jnobgabnnbdhjompaagbfbjiimplamll'


def _inject_nasca_simulation(page: Page) -> None:
    """Inject a JavaScript shim that:
    1. Creates the NASCA <object> element so Vdisk detects the extension.
    2. Responds to nscMsgCxrReq window messages with the Windows computer name.
    3. Intercepts both fetch() and XMLHttpRequest.send() to patch the
       loggings/vm request body — replacing vm_name:"" with the real computer
       name so the server records the correct access location (not 'PC(사내)').
    """
    computer_name = os.environ.get('COMPUTERNAME', 'PC')
    logging.info("Injecting NASCA simulation for device name: %s", computer_name)

    script = f"""
(function() {{
    const EXT_ID = '{_NASCA_EXT_ID}';
    const PC_NAME = '{computer_name}';

    // 0. Hide webdriver flag so Vdisk doesn't skip the NASCA flow for automation
    try {{
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
    }} catch(e) {{}}

    // 1. Inject the <object> element the real NASCA extension injects
    if (!document.getElementById(EXT_ID)) {{
        var obj = document.createElement('object');
        obj.id = EXT_ID;
        obj.style.display = 'none';
        obj.width = 0;
        obj.height = 0;
        (document.documentElement || document.body).appendChild(obj);
    }}

    // Helper: parse JSON body and replace vm_name:"" with PC_NAME
    function _patchVmBody(body) {{
        try {{
            var parsed = JSON.parse(body);
            if ('vm_name' in parsed) {{
                var old = parsed.vm_name;
                parsed.vm_name = PC_NAME;
                console.log('FETCH_SPY loggings/vm vm_name: "' + old + '" -> "' + PC_NAME + '"');
                return JSON.stringify(parsed);
            }}
        }} catch(e) {{}}
        return body;
    }}

    // 2. Intercept fetch() — patch loggings/vm body, log file/upload body
    const _origFetch = window.fetch;
    window.fetch = function(url, opts) {{
        var urlStr = (typeof url === 'string') ? url : ((url && url.url) || '');
        if (urlStr.includes('loggings/vm')) {{
            var body = (opts && opts.body) ? opts.body : '';
            if (typeof body === 'string') {{
                body = _patchVmBody(body);
                opts = Object.assign({{}}, opts, {{body: body}});
            }}
            return _origFetch.apply(this, [url, opts]);
        }}
        if (urlStr.includes('file/upload')) {{
            var b = (opts && opts.body) ? opts.body : '';
            if (b instanceof FormData) {{
                var pairs = [];
                b.forEach(function(v, k) {{ if (typeof v === 'string') pairs.push(k + '=' + v); }});
                console.log('FETCH_SPY file/upload FormData: ' + pairs.join(', '));
            }} else if (typeof b === 'string') {{
                console.log('FETCH_SPY file/upload body: ' + b.substring(0, 300));
            }}
        }}
        return _origFetch.apply(this, arguments);
    }};

    // 3. Intercept XHR — patch loggings/vm body
    var _origOpen = XMLHttpRequest.prototype.open;
    var _origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {{
        this._xhrUrl = (url || '').toString();
        return _origOpen.apply(this, arguments);
    }};
    XMLHttpRequest.prototype.send = function(body) {{
        if (this._xhrUrl && this._xhrUrl.includes('loggings/vm') && typeof body === 'string') {{
            body = _patchVmBody(body);
        }}
        return _origSend.call(this, body);
    }};

    // 4. Respond to nscMsgCxrReq window messages (NASCA protocol)
    window.addEventListener('message', function(event) {{
        if (!event.data || event.data.type !== 'nscMsgCxrReq') return;
        console.log('NASCA_SIM: received ' + JSON.stringify(event.data));
        var payload = {{PC_NAME: PC_NAME, ResultCode: '0'}};
        var outVal = btoa(JSON.stringify(payload));
        event.source.postMessage(
            {{type: 'nscMsgCxrRes', result: '0', outVal: outVal}},
            event.origin
        );
        console.log('NASCA_SIM: responded with PC_NAME=' + PC_NAME);
    }}, false);
}})();
"""
    try:
        page.add_init_script(script)
    except Exception as e:
        logging.warning("NASCA simulation injection failed: %s", e)


def _setup_vm_name_route(page: Page, computer_name: str) -> None:
    """Use Playwright's network-level routing to patch loggings/vm request body.

    This is more reliable than JS injection: it intercepts at the network layer,
    so it works regardless of which JS framework made the request, which frame
    it came from, or when it was called.
    """
    def _handle_vm_route(route, request):
        if request.method == 'POST' and 'loggings/vm' in request.url:
            try:
                body_str = request.post_data or '{}'
                body = json.loads(body_str)
                old_name = body.get('vm_name', '')
                body['vm_name'] = computer_name
                patched = json.dumps(body)
                logging.info("ROUTE loggings/vm vm_name: %r -> %r", old_name, computer_name)
                route.continue_(post_data=patched,
                                headers={**request.headers,
                                         'content-length': str(len(patched.encode()))})
                return
            except Exception as e:
                logging.warning("ROUTE loggings/vm patch failed: %s", e)
        route.continue_()

    page.route('**/loggings/vm**', _handle_vm_route)
    logging.info("Network route installed: loggings/vm vm_name will be set to %s", computer_name)


def _do_upload(page: Page, context: BrowserContext, path: str,
               config: Dict[str, Any], browser_config: Dict[str, Any],
               skip_login: bool = False) -> Dict[str, Any]:
    """Core upload logic shared between profile and non-profile flows."""
    computer_name = os.environ.get('COMPUTERNAME', 'PC')

    # Network-level interception: patch loggings/vm vm_name before it hits the server
    _setup_vm_name_route(page, computer_name)

    # JS-level shim: fake NASCA element + nscMsgCxrReq handler (belt-and-suspenders)
    _inject_nasca_simulation(page)
    page.on("console", lambda msg: logging.info("BROWSER: %s", msg.text)
            if any(msg.text.startswith(p) for p in ("NASCA", "FETCH_SPY")) else None)

    def _log_interesting_request(request):
        if request.method != 'POST':
            return
        url = request.url
        if any(x in url for x in ('login/auth', 'vdisk/file/upload', 'checksw', 'loggings')):
            logging.info("REQ %s", url)
            try:
                body = request.post_data or ''
                if isinstance(body, bytes):
                    body = body.decode('utf-8', errors='replace')
                # Redact password before logging
                if 'login/auth' in url:
                    try:
                        parsed = json.loads(body)
                        if 'password' in parsed:
                            parsed['password'] = '***'
                        body = json.dumps(parsed)
                    except Exception:
                        body = re.sub(r'("password"\s*:\s*)"[^"]*"', r'\1"***"', body)
                logging.info("  BODY: %s", body[:500])
            except Exception:
                pass

    def _log_interesting_response(response):
        url = response.url
        if any(x in url for x in ('vdisk/file/upload', 'loggings/vm',
                                   'checksw', 'getsoftwarebytype')):
            try:
                logging.info("RESP %s %d: %s", url, response.status, response.text()[:800])
            except Exception:
                pass

    page.on("request", _log_interesting_request)
    page.on("response", _log_interesting_response)

    if skip_login:
        # With Chrome profile, navigate directly and check if still logged in
        upload_page_url = browser_config["upload_page_url"]
        page.goto(upload_page_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        # If redirected to login page, do form login then navigate back
        if page.query_selector(browser_config.get("password_selector", "")):
            logging.info("SSO session expired, falling back to form login")
            _login(page, context, config, browser_config)
            _navigate_to_upload(page, browser_config)
    else:
        _login(page, context, config, browser_config)
        _navigate_to_upload(page, browser_config)

    # Log the 현재 접속위치 (current access location) to confirm session identity
    try:
        loc_el = page.query_selector("xpath=//*[contains(text(),'접속위치') or contains(text(),'Access')]/..")
        if loc_el:
            logging.info("PAGE access location block: %s", loc_el.inner_text()[:200])
        # Also try to get all text containing SEC or PC from the page header area
        all_text = page.eval_on_selector("body", "el => el.innerText.substring(0, 3000)")
        for line in all_text.split('\n'):
            if '접속위치' in line or 'SEC-' in line:
                logging.info("PAGE text: %s", line.strip())
    except Exception as e:
        logging.debug("Page location read error: %s", e)

    upload_modal_button = page.query_selector(browser_config["upload_modal_button_selector"])
    if upload_modal_button:
        upload_modal_button.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

    file_select_button = page.query_selector(browser_config["file_select_button_selector"])
    if file_select_button:
        with page.expect_file_chooser(timeout=15000) as file_chooser_info:
            file_select_button.click(force=True)
        file_chooser_info.value.set_files(path)
        page.wait_for_timeout(2000)

    upload_confirm = page.query_selector(browser_config["upload_confirm_button_selector"])
    if upload_confirm:
        upload_confirm.click(force=True)
        page.wait_for_timeout(15000)

    verification_success = False
    try:
        page.goto(browser_config["upload_page_url"], wait_until="networkidle")
        page.wait_for_timeout(2000)
        file_name = os.path.basename(path)
        if page.query_selector(f"xpath=//*[contains(text(), '{file_name}')]"):
            logging.info("Upload verified: %s found in file list", file_name)
            verification_success = True
        else:
            logging.warning("Upload not verified: %s not found in file list", file_name)
    except Exception as e:
        logging.warning("Upload verification error: %s", e)

    return {"status": "browser-uploaded", "path": path, "verified": verification_success}


def upload_file_via_browser(path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    browser_config = _browser_config(config)
    with sync_playwright() as playwright:
        temp_profile_dir = None
        context = None
        browser = None

        # Prefer Chrome with user profile: inherits NASCA extension and Samsung SSO
        # session, so Vdisk records the correct device name instead of 'PC(사내)'.
        chrome_user_data = _get_chrome_user_data_dir()
        if chrome_user_data:
            temp_profile_dir = _copy_chrome_profile(chrome_user_data)
        if temp_profile_dir:
            context = _launch_with_chrome_profile(
                playwright, temp_profile_dir, headless=browser_config["headless"]
            )

        # Fall back to fresh browser if profile approach failed
        if context is None:
            if temp_profile_dir:
                shutil.rmtree(temp_profile_dir, ignore_errors=True)
                temp_profile_dir = None
            browser = _launch_browser(playwright, headless=browser_config["headless"])
            context = _new_context(browser)

        try:
            page = context.new_page()
            result = _do_upload(
                page, context, path, config, browser_config,
                skip_login=(temp_profile_dir is not None)
            )
            return result
        finally:
            context.close()
            if browser:
                browser.close()
            if temp_profile_dir:
                shutil.rmtree(temp_profile_dir, ignore_errors=True)


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
    """Verify credentials and save session cookies. Tries Chrome profile first."""
    browser_config = _browser_config(config)
    try:
        with sync_playwright() as playwright:
            temp_profile_dir = None
            context = None
            browser = None

            chrome_user_data = _get_chrome_user_data_dir()
            if chrome_user_data:
                temp_profile_dir = _copy_chrome_profile(chrome_user_data)
            if temp_profile_dir:
                context = _launch_with_chrome_profile(playwright, temp_profile_dir, headless=True)

            if context is None:
                if temp_profile_dir:
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
                    temp_profile_dir = None
                browser = _launch_browser(playwright, headless=True)
                context = _new_context(browser)

            try:
                page = context.new_page()
                _inject_nasca_simulation(page)
                login_url = browser_config["login_url"]

                logging.info("[verify_login] Navigating to %s", login_url)
                page.goto(login_url)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                logging.info("[verify_login] Page loaded. URL: %s", page.url)

                # With Chrome profile: SSO session might already be valid
                if temp_profile_dir and not page.query_selector(browser_config["password_selector"]):
                    logging.info("[verify_login] SSO session still valid (no login form)")
                    _save_cookies(context, config)
                    return True

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
            finally:
                context.close()
                if browser:
                    browser.close()
                if temp_profile_dir:
                    shutil.rmtree(temp_profile_dir, ignore_errors=True)
    except Exception as e:
        logging.error("[verify_login] Error: %s", e, exc_info=True)
        return False


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
