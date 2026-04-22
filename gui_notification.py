import tkinter as tk


class UploadNotification:
    W, H = 380, 134
    ICON_SIZE = 40

    COLORS = {
        'bg':           '#ffffff',
        'border':       '#c8c8c8',
        'title':        '#1a1a1a',
        'body':         '#3d3d3d',
        'dim':          '#939393',
        'icon_blue':    '#0078d4',
        'icon_blue2':   '#005fb8',
        'btn_primary':  '#0078d4',
        'btn_primary_h':'#005fb8',
        'btn_secondary':'#f0f0f0',
        'btn_sec_h':    '#e0e0e0',
        'btn_sec_fg':   '#1a1a1a',
    }

    def __init__(self, content_preview: str, content_type: str = '텍스트'):
        self.result = None
        if len(content_preview) > 80:
            self.content_preview = content_preview[:79] + '…'
        else:
            self.content_preview = content_preview
        self.content_type = content_type
        self.is_closed = False
        self.window = None
        self.timer_label = None
        self.remaining_time = 0

    def show(self, timeout_seconds: int = 10) -> str:
        try:
            self._build(timeout_seconds)
        except Exception as e:
            print(f'GUI Error: {e}')
        return self.result or 'skip'

    # ── 창 생성 ──────────────────────────────────────────────────────────
    def _build(self, timeout: int):
        win = tk.Tk()
        self.window = win
        win.overrideredirect(True)
        win.attributes('-topmost', True)

        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = sw - self.W - 20
        y = sh - self.H - 80
        win.geometry(f'{self.W}x{self.H}+{x}+{y}')
        win.configure(bg=self.COLORS['border'])

        # 카드 (1px 테두리 = border color 배경 위에 1px 안쪽)
        card = tk.Frame(win, bg=self.COLORS['bg'])
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ── 왼쪽: 아이콘 영역 ────────────────────────────────────────────
        icon_col = tk.Frame(card, bg=self.COLORS['bg'],
                            width=self.ICON_SIZE + 22)
        icon_col.pack(side=tk.LEFT, fill=tk.Y)
        icon_col.pack_propagate(False)

        ic = self.ICON_SIZE
        canvas = tk.Canvas(icon_col, width=ic, height=ic,
                           bg=self.COLORS['bg'], highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor='center')
        self._draw_app_icon(canvas, ic)

        # ── 오른쪽: 텍스트 + 버튼 영역 ───────────────────────────────────
        right = tk.Frame(card, bg=self.COLORS['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                   padx=(0, 12), pady=8)

        # 상단: 앱 이름 + 컨트롤
        top = tk.Frame(right, bg=self.COLORS['bg'])
        top.pack(fill=tk.X)

        tk.Label(top, text='Vdisk Uploader',
                 bg=self.COLORS['bg'], fg=self.COLORS['title'],
                 font=('Segoe UI Semibold', 9)).pack(side=tk.LEFT)

        self._icon_btn(top, '✕', self._on_skip).pack(side=tk.RIGHT, padx=(2, 0))
        self._icon_btn(top, '···', None).pack(side=tk.RIGHT, padx=(0, 4))

        # 액션 버튼을 먼저 bottom에 pack → 버튼 공간 먼저 확보
        actions = tk.Frame(right, bg=self.COLORS['bg'])
        actions.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        self._action_btn(
            actions, '업로드',
            self.COLORS['btn_primary'], self.COLORS['btn_primary_h'],
            'white', self._on_upload
        ).pack(side=tk.LEFT, padx=(0, 5))

        self._action_btn(
            actions, '무시',
            self.COLORS['btn_secondary'], self.COLORS['btn_sec_h'],
            self.COLORS['btn_sec_fg'], self._on_skip
        ).pack(side=tk.LEFT)

        self.timer_label = tk.Label(actions, text=f'{timeout}초',
                                    bg=self.COLORS['bg'], fg=self.COLORS['dim'],
                                    font=('Segoe UI', 8))
        self.timer_label.pack(side=tk.RIGHT)

        # 본문: 컨텐츠 타입 + 실제 내용 미리보기 (한 줄 고정, 넘치면 말줄임)
        tk.Label(right, text=self.content_type,
                 bg=self.COLORS['bg'], fg=self.COLORS['body'],
                 font=('Segoe UI', 8, 'bold'), justify=tk.LEFT
                 ).pack(anchor='w', pady=(3, 0))

        tk.Label(right, text=self.content_preview,
                 bg=self.COLORS['bg'], fg=self.COLORS['dim'],
                 font=('Segoe UI', 8), justify=tk.LEFT, wraplength=290
                 ).pack(anchor='w')

        self.remaining_time = timeout
        self._tick()
        win.protocol('WM_DELETE_WINDOW', self._on_skip)
        try:
            win.mainloop()
        except Exception:
            pass

    # ── 아이콘 드로잉 (둥근 모서리 파란 사각형 + 업로드 화살표) ───────────
    def _draw_app_icon(self, canvas: tk.Canvas, size: int):
        c = self.COLORS['icon_blue']
        r = 7  # 모서리 반지름

        # 둥근 모서리 사각형 (arc 4개 + 직사각형 3개 조합)
        canvas.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=c, outline='')
        canvas.create_arc(size-r*2, 0, size, r*2, start=0, extent=90, fill=c, outline='')
        canvas.create_arc(0, size-r*2, r*2, size, start=180, extent=90, fill=c, outline='')
        canvas.create_arc(size-r*2, size-r*2, size, size, start=270, extent=90, fill=c, outline='')
        canvas.create_rectangle(r, 0, size-r, size, fill=c, outline='')
        canvas.create_rectangle(0, r, size, size-r, fill=c, outline='')

        # 업로드 화살표 (흰색)
        cx, cy = size // 2, size // 2
        # 화살표 몸통
        canvas.create_rectangle(cx-2, cy+1, cx+2, cy+11, fill='white', outline='')
        # 화살표 머리
        canvas.create_polygon(
            cx, cy-10,
            cx-7, cy+2,
            cx-3, cy+2,
            cx-3, cy+2,
            cx+3, cy+2,
            cx+7, cy+2,
            fill='white', outline=''
        )
        # 화살표 머리 (삼각형)
        canvas.create_polygon(cx, cy-9, cx-7, cy+2, cx+7, cy+2,
                               fill='white', outline='')

    # ── 헬퍼: 컨트롤 아이콘 버튼 ─────────────────────────────────────────
    def _icon_btn(self, parent, text: str, command):
        lbl = tk.Label(parent, text=text,
                       bg=self.COLORS['bg'], fg=self.COLORS['dim'],
                       font=('Segoe UI', 9), cursor='hand2' if command else 'arrow')
        if command:
            lbl.bind('<Button-1>', lambda e: command())
            lbl.bind('<Enter>', lambda e: lbl.config(fg=self.COLORS['title']))
            lbl.bind('<Leave>', lambda e: lbl.config(fg=self.COLORS['dim']))
        return lbl

    # ── 헬퍼: 액션 버튼 ──────────────────────────────────────────────────
    def _action_btn(self, parent, text, bg, hover_bg, fg, command):
        btn = tk.Button(parent, text=text, bg=bg, fg=fg,
                        activebackground=hover_bg, activeforeground=fg,
                        font=('Segoe UI', 8, 'bold'),
                        bd=0, relief='flat', cursor='hand2',
                        padx=12, pady=3, command=command)
        btn.bind('<Enter>', lambda e: btn.config(bg=hover_bg))
        btn.bind('<Leave>', lambda e: btn.config(bg=bg))
        return btn

    # ── 타이머 ───────────────────────────────────────────────────────────
    def _tick(self):
        if not self.is_closed and self.window:
            self.remaining_time -= 1
            self.timer_label.config(text=f'{self.remaining_time}초')
            if self.remaining_time <= 0:
                self.result = 'skip'
                self._close()
            else:
                self.window.after(1000, self._tick)

    def _on_upload(self):
        self.result = 'upload'
        self._close()

    def _on_skip(self):
        self.result = 'skip'
        self._close()

    def _close(self):
        if self.window and not self.is_closed:
            self.is_closed = True
            try:
                self.window.destroy()
            except Exception:
                pass


def show_upload_prompt(content_preview: str, content_type: str = '텍스트',
                       timeout: int = 10) -> bool:
    return UploadNotification(content_preview, content_type).show(timeout) == 'upload'


class UploadCompleteNotification:
    W, H = 320, 80

    COLORS = {
        'bg':      '#ffffff',
        'border':  '#c8c8c8',
        'title':   '#1a1a1a',
        'dim':     '#939393',
        'success': '#107c10',
        'error':   '#c42b1c',
    }

    def __init__(self, content_type: str, success: bool):
        self.content_type = content_type
        self.success = success
        self.window = None
        self.is_closed = False

    def show(self, timeout: int = 4):
        try:
            self._build(timeout)
        except Exception as e:
            print(f'GUI Error: {e}')

    def _build(self, timeout: int):
        win = tk.Tk()
        self.window = win
        win.overrideredirect(True)
        win.attributes('-topmost', True)

        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = sw - self.W - 20
        y = sh - self.H - 80
        win.geometry(f'{self.W}x{self.H}+{x}+{y}')
        win.configure(bg=self.COLORS['border'])

        card = tk.Frame(win, bg=self.COLORS['bg'])
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 왼쪽: 결과 아이콘
        icon_col = tk.Frame(card, bg=self.COLORS['bg'], width=56)
        icon_col.pack(side=tk.LEFT, fill=tk.Y)
        icon_col.pack_propagate(False)

        icon_color = self.COLORS['success'] if self.success else self.COLORS['error']
        icon_char  = '✓' if self.success else '✕'
        ic = 32
        c = tk.Canvas(icon_col, width=ic, height=ic,
                      bg=self.COLORS['bg'], highlightthickness=0)
        c.place(relx=0.5, rely=0.5, anchor='center')
        c.create_oval(0, 0, ic, ic, fill=icon_color, outline='')
        c.create_text(ic//2, ic//2, text=icon_char,
                      fill='white', font=('Segoe UI', 13, 'bold'))

        # 오른쪽: 텍스트
        right = tk.Frame(card, bg=self.COLORS['bg'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        status_text = '업로드 완료' if self.success else '업로드 실패'
        status_color = self.COLORS['success'] if self.success else self.COLORS['error']

        tk.Label(right, text='Vdisk Uploader',
                 bg=self.COLORS['bg'], fg=self.COLORS['title'],
                 font=('Segoe UI Semibold', 9)
                 ).pack(anchor='w', pady=(12, 0))

        tk.Label(right, text=f'{self.content_type} {status_text}',
                 bg=self.COLORS['bg'], fg=status_color,
                 font=('Segoe UI', 8, 'bold')
                 ).pack(anchor='w', pady=(2, 0))

        self.remaining = timeout
        self.timer = tk.Label(right, text=f'{timeout}초 후 닫힘',
                              bg=self.COLORS['bg'], fg=self.COLORS['dim'],
                              font=('Segoe UI', 7))
        self.timer.pack(anchor='w')

        self._tick()
        win.bind('<Button-1>', lambda e: self._close())
        try:
            win.mainloop()
        except Exception:
            pass

    def _tick(self):
        if not self.is_closed and self.window:
            self.remaining -= 1
            if self.remaining <= 0:
                self._close()
            else:
                self.timer.config(text=f'{self.remaining}초 후 닫힘')
                self.window.after(1000, self._tick)

    def _close(self):
        if self.window and not self.is_closed:
            self.is_closed = True
            try:
                self.window.destroy()
            except Exception:
                pass


def show_upload_complete(content_type: str, success: bool = True, timeout: int = 4):
    UploadCompleteNotification(content_type, success).show(timeout)
