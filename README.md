# Vdisk Clipboard Uploader

Windows에서 클립보드 내용을 Samsung Smart Office Vdisk로 자동 업로드하는 프로그램 샘플입니다.

## 주요 기능

- 클립보드 텍스트, 이미지, 파일 드롭 목록을 감시
- 새 클립보드 변경이 감지되면 자동 업로드 시도
- `browser` 또는 `api` 업로드 모드 선택 가능
- 설정 파일(`config.json`)로 관리
- `init`, `run`, `status`, `upload-text` 명령 지원

## 설치

이 프로그램은 Python 3.9+에서 동작합니다.

1. Python이 설치되어 있는지 확인합니다.
2. 필요한 패키지를 설치합니다:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` 파일을 생성하고 로그인 정보를 설정합니다:
   ```bash
   cp .env.example .env
   ```
   `.env` 파일을 편집해서 실제 로그인 정보를 입력하세요:
   ```
   VDISK_USERNAME=your.username@samsung.com
   VDISK_PASSWORD=your_password
   VDISK_AUTH_TOKEN=your_api_token
   ```
4. 프로그램을 초기화하고 실행합니다:
   ```powershell
   python main.py init --upload-method browser
   python main.py run
   ```

### 보안 주의사항

- `.env` 파일에는 민감한 정보(비밀번호, API 토큰)가 저장됩니다.
- `.env` 파일은 `.gitignore`에 포함되어 버전 관리에서 제외됩니다.
- 실제 운영 환경에서는 `.env` 파일의 권한을 적절히 설정하세요.

## 브라우저 자동화 업로드

API가 없는 경우 Playwright를 사용해 브라우저로 로그인하고 파일을 직접 업로드할 수 있습니다. 이 모드는 `upload_method: "browser"`일 때 사용됩니다.

### 쿠키 저장 및 세션 재사용

프로그램은 로그인 후 브라우저 쿠키를 `browser_cookies.json` 파일에 저장하고, 다음 실행 시 재사용합니다. 이를 통해 반복적인 로그인을 피할 수 있습니다.

`config.json` 예시:

```json
{
  "upload_method": "browser",
  "upload_folder": "/clipboard",
  "watch_text": true,
  "watch_images": true,
  "watch_files": true,
  "poll_interval": 1.0,
  "dry_run": true,
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
    "headless": true,
    "max_wait": 30,
    "reuse_session": true
  }
}
```

### 브라우저 업로드 동작 흐름

Playwright는 내부적으로 CDP를 사용하므로 별도의 CDP 구현이 필요하지 않습니다. 하지만 더 낮은 수준의 제어가 필요한 경우 다음 옵션들을 고려할 수 있습니다:

1. **Playwright의 CDP 연결**: `playwright.chromium.connect_over_cdp()`를 사용해 기존 Chrome 인스턴스에 연결
2. **직접 CDP 사용**: `pyppeteer`나 `selenium` + ChromeDriver로 CDP 직접 제어
3. **Chrome 확장 프로그램**: Vdisk 업로드를 위한 전용 Chrome 확장 프로그램 개발

현재 구현은 Playwright를 사용하므로 대부분의 사용 사례에서 충분합니다.
  }
}
```

### 브라우저 업로드 동작 흐름

1. 로그인 페이지로 이동
2. 사용자 이름/비밀번호 입력
3. 업로드 페이지로 이동 (필요 시)
4. 파일 입력 필드에 생성된 임시 파일 지정
5. 업로드 확인 버튼 클릭

## 사용법

- `python main.py init` - 설정 파일 생성 또는 업데이트
- `python main.py run` - 클립보드 감시 및 자동 업로드 시작
- `python main.py status` - 현재 설정과 상태 확인
- `python main.py upload-text --text "Hello"` - 즉시 텍스트 업로드
- `python main.py simulate --dry-run` - 텍스트, 이미지, 파일 업로드 흐름 시뮬레이션

## 주의

- 실제 Samsung Smart Office Vdisk UI는 사이트 구조와 셀렉터가 바뀔 수 있습니다.
- `config.json`의 `browser` 설정에서 셀렉터를 실제 페이지에 맞게 수정해야 합니다.
- 실제 업로드를 테스트하려면 `dry_run`을 `false`로 설정합니다.
