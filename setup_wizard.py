import os
import sys
import threading
import tkinter as tk
import winreg


def _set_env_value(key: str, value: str, env_path: str) -> None:
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith(f'{key}='):
            lines[i] = f'{key}={value}\n'
            found = True
            break
    if not found:
        lines.append(f'{key}={value}\n')
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def register_autostart() -> None:
    if getattr(sys, 'frozen', False):
        cmd = f'"{sys.executable}"'
    else:
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'main.py'))
        cmd = f'"{sys.executable}" "{script}" run'
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, 'VdiskUploader', 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
    except Exception as e:
        print(f'Autostart registration failed: {e}')


def is_setup_complete() -> bool:
    return bool(os.getenv('VDISK_USERNAME') and os.getenv('VDISK_PASSWORD'))


class SetupWizard:
    COLORS = {
        'bg':         '#f3f3f3',
        'card':       '#ffffff',
        'header':     '#0078d4',
        'title':      '#1a1a1a',
        'label':      '#3d3d3d',
        'dim':        '#939393',
        'border':     '#d0d0d0',
        'primary':    '#0078d4',
        'primary_h':  '#005fb8',
        'success':    '#107c10',
        'error':      '#c42b1c',
    }

    def __init__(self, env_path: str):
        self.env_path = env_path
        self.window = None
        self.username_var = None
        self.password_var = None
        self.status_label = None
        self.login_btn = None
        self.result = False

    def run(self) -> bool:
        win = tk.Tk()
        self.window = win
        win.title('Vdisk Uploader 초기 설정')
        win.resizable(False, False)
        win.configure(bg=self.COLORS['bg'])

        w, h = 440, 380
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f'{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}')

        self._build()
        win.mainloop()
        return self.result

    def _build(self):
        win = self.window

        # ── 헤더 ─────────────────────────────────────────────────────────
        header = tk.Frame(win, bg=self.COLORS['header'], height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text='Vdisk Uploader',
                 bg=self.COLORS['header'], fg='white',
                 font=('Segoe UI', 15, 'bold')).pack(side=tk.LEFT, padx=24, pady=18)

        # ── 본문 ─────────────────────────────────────────────────────────
        body = tk.Frame(win, bg=self.COLORS['bg'])
        body.pack(fill=tk.BOTH, expand=True, padx=32, pady=24)

        tk.Label(body, text='Samsung 계정 정보를 입력하세요.',
                 bg=self.COLORS['bg'], fg=self.COLORS['dim'],
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 20))

        # 사번 입력
        tk.Label(body, text='사번 (Samsung ID)',
                 bg=self.COLORS['bg'], fg=self.COLORS['label'],
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        self.username_var = tk.StringVar()
        self._make_entry(body, self.username_var, show=None).pack(
            fill=tk.X, pady=(4, 14))

        # 비밀번호 입력
        tk.Label(body, text='비밀번호',
                 bg=self.COLORS['bg'], fg=self.COLORS['label'],
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        self.password_var = tk.StringVar()
        pw_entry = self._make_entry(body, self.password_var, show='●')
        pw_entry.pack(fill=tk.X, pady=(4, 20))
        pw_entry.winfo_children()[0].bind('<Return>', lambda e: self._start_verify())

        # 상태 메시지
        self.status_label = tk.Label(body, text='',
                                     bg=self.COLORS['bg'],
                                     font=('Segoe UI', 8), justify=tk.LEFT)
        self.status_label.pack(anchor='w', pady=(0, 10))

        # 로그인 확인 버튼
        self.login_btn = tk.Button(
            body, text='로그인 확인',
            bg=self.COLORS['primary'], fg='white',
            activebackground=self.COLORS['primary_h'], activeforeground='white',
            font=('Segoe UI', 10, 'bold'),
            bd=0, relief='flat', cursor='hand2',
            padx=24, pady=8,
            command=self._start_verify
        )
        self.login_btn.pack(anchor='w')
        self.login_btn.bind('<Enter>', lambda e: self.login_btn.config(bg=self.COLORS['primary_h']))
        self.login_btn.bind('<Leave>', lambda e: self.login_btn.config(bg=self.COLORS['primary']))

    def _make_entry(self, parent, var, show):
        frame = tk.Frame(parent, bg=self.COLORS['border'], padx=1, pady=1)
        inner = tk.Frame(frame, bg='white')
        inner.pack(fill=tk.X)
        entry = tk.Entry(inner, textvariable=var, show=show,
                         font=('Segoe UI', 10), relief='flat', bd=0,
                         bg='white', fg=self.COLORS['title'])
        entry.pack(fill=tk.X, padx=8, pady=6)
        return frame

    def _start_verify(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()

        if not username or not password:
            self._set_status('사번과 비밀번호를 모두 입력해주세요.', 'error')
            return

        self.login_btn.config(state='disabled', text='확인 중...')
        self._set_status('로그인을 확인하고 있습니다. 잠시 기다려주세요...', 'dim')

        threading.Thread(
            target=self._verify_thread,
            args=(username, password),
            daemon=True
        ).start()

    def _verify_thread(self, username: str, password: str):
        import logging
        try:
            from browser_uploader import verify_login
            from config import load_config
            config = load_config()
            config['username'] = username
            config['password'] = password
            success = verify_login(username, password, config)
        except Exception as e:
            logging.error('Verify thread error: %s', e, exc_info=True)
            success = False
        self.window.after(0, self._on_verify_done, success, username, password)

    def _on_verify_done(self, success: bool, username: str, password: str):
        if success:
            _set_env_value('VDISK_USERNAME', username, self.env_path)
            _set_env_value('VDISK_PASSWORD', password, self.env_path)
            register_autostart()
            self._set_status('✓ 로그인 성공! 자동 시작이 등록되었습니다.', 'success')
            self.login_btn.config(text='시작하기', state='normal',
                                  bg=self.COLORS['primary'],
                                  command=self._finish)
            self.login_btn.bind('<Enter>', lambda e: self.login_btn.config(bg=self.COLORS['primary_h']))
            self.login_btn.bind('<Leave>', lambda e: self.login_btn.config(bg=self.COLORS['primary']))
        else:
            self._set_status('✕ 로그인 실패. 사번과 비밀번호를 확인해주세요.', 'error')
            self.login_btn.config(text='다시 시도', state='normal')

    def _set_status(self, text: str, style: str):
        color = {'success': self.COLORS['success'],
                 'error': self.COLORS['error'],
                 'dim': self.COLORS['dim']}.get(style, self.COLORS['dim'])
        self.status_label.config(text=text, fg=color)

    def _finish(self):
        self.result = True
        self.window.destroy()


def run_setup_if_needed(env_path: str) -> bool:
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)

    if is_setup_complete():
        return True

    wizard = SetupWizard(env_path)
    return wizard.run()
