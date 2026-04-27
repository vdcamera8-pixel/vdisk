# Vdisk Clipboard Uploader

Windows에서 클립보드 내용을 Samsung Smart Office Vdisk로 자동 업로드하는 프로그램입니다.

## 주요 기능

- 클립보드 텍스트, 이미지, 파일 드롭 목록을 감시
- 새 클립보드 변경이 감지되면 자동 업로드 시도
- Chrome 사용자 프로필을 활용해 올바른 접속위치(`SEC-AI-D-03354(사내)`) 유지
- 시스템 트레이에서 실행, 부팅 시 자동 시작
- `browser` 또는 `api` 업로드 모드 선택 가능

---

## Windows 설치 (릴리즈 버전 권장)

### 1. 다운로드

[Releases](https://github.com/vdcamera8-pixel/vdisk/releases/latest) 페이지에서 `VdiskUploader-vX.X.X-windows.zip`을 다운로드합니다.

### 2. 압축 해제

다운로드한 zip 파일을 원하는 폴더에 압축 해제합니다.

### 3. install.bat 실행

압축 해제된 폴더에서 `install.bat`을 **더블클릭**합니다.

설치 스크립트가 자동으로:
- `%APPDATA%\VdiskUploader\` 폴더에 파일 복사
- 바탕화면에 바로가기 생성
- 부팅 시 자동 시작 등록

### 4. 최초 실행 시 설정

처음 실행 시 설정 마법사가 표시됩니다. 아래 정보를 입력하세요:

| 항목 | 예시 |
|------|------|
| Samsung 사번 (ID) | `jaeyong2.kim` |
| 비밀번호 | Vdisk 로그인 비밀번호 |

설정은 `%APPDATA%\VdiskUploader\.env`에 저장됩니다.

### 5. 사용

- 설치 후 **바탕화면 바로가기** 또는 시스템 트레이에서 실행
- 클립보드에 텍스트/이미지를 복사하면 자동으로 업로드 확인 팝업이 표시됩니다
- 업로드된 파일은 Vdisk MyFiles에서 확인할 수 있습니다

### 6. 제거

```powershell
# 자동 시작 제거
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v VdiskUploader /f

# 파일 삭제
Remove-Item "$env:APPDATA\VdiskUploader" -Recurse -Force

# 바탕화면 바로가기 삭제
Remove-Item "$env:USERPROFILE\Desktop\Vdisk Uploader.lnk" -Force
```

---

## 소스에서 직접 실행 (개발자용)

Python 3.9+ 환경이 필요합니다.

### 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### .env 파일 생성

```bash
cp .env.example .env
```

`.env` 파일을 편집해서 실제 로그인 정보를 입력하세요:

```
VDISK_USERNAME=your.username
VDISK_PASSWORD=your_password
```

### 실행

```powershell
python main.py run
```

### 주요 명령어

| 명령어 | 설명 |
|--------|------|
| `python main.py init` | 설정 파일 생성 또는 업데이트 |
| `python main.py run` | 클립보드 감시 및 자동 업로드 시작 |
| `python main.py status` | 현재 설정과 상태 확인 |
| `python main.py upload-text --text "Hello"` | 텍스트 즉시 업로드 |
| `python main.py simulate --dry-run` | 업로드 흐름 시뮬레이션 (실제 업로드 없음) |

---

## config.json 설정

`%APPDATA%\VdiskUploader\config.json` (릴리즈) 또는 `config.json` (소스 실행)에서 설정을 변경할 수 있습니다.

```json
{
  "upload_method": "browser",
  "watch_text": true,
  "watch_images": true,
  "watch_files": true,
  "poll_interval": 1.0,
  "dry_run": false,
  "enable_upload_prompt": true,
  "browser": {
    "login_url": "https://smartoffice-in.samsung.net/ko-kr/Vdisk",
    "username_selector": "#loginId",
    "password_selector": "#mbrPswd",
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

| 항목 | 설명 |
|------|------|
| `dry_run` | `true`이면 실제 업로드 없이 동작만 시뮬레이션 |
| `enable_upload_prompt` | `true`이면 업로드 전 확인 팝업 표시 |
| `poll_interval` | 클립보드 감시 주기 (초) |
| `headless` | `true`이면 브라우저 창 숨김 |

---

## 보안 주의사항

- `.env` 파일에는 비밀번호가 저장됩니다. 타인과 공유하지 마세요.
- 로그 파일(`%APPDATA%\VdiskUploader\vdisk_uploader.log`)에는 비밀번호가 기록되지 않습니다.
- `.env` 파일은 `.gitignore`에 포함되어 버전 관리에서 제외됩니다.

---

## 문제 해결

### 업로드 위치가 `PC(사내)`로 표시되는 경우

v1.1.0부터 자동으로 수정됩니다. 구버전 사용 중이라면 최신 릴리즈로 업데이트하세요.

### 업로드가 안 되는 경우

1. 로그 파일 확인: `%APPDATA%\VdiskUploader\vdisk_uploader.log`
2. `config.json`의 `dry_run`이 `false`인지 확인
3. Samsung Smart Office Vdisk 사이트의 셀렉터가 변경된 경우 `config.json`의 `browser` 항목을 실제 페이지에 맞게 수정

### 브라우저 창이 뜨는 경우

`config.json`에서 `"headless": true`로 설정하면 백그라운드에서 실행됩니다.
