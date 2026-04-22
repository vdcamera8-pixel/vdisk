import threading
from typing import Callable

from PIL import Image, ImageDraw
import pystray


def _create_icon_image() -> Image.Image:
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=12, fill='#0078d4')

    cx, cy = size // 2, size // 2
    # Arrow body
    draw.rectangle([cx - 3, cy + 2, cx + 3, cy + 16], fill='white')
    # Arrow head (triangle)
    draw.polygon([cx, cy - 14, cx - 10, cy + 4, cx + 10, cy + 4], fill='white')

    return img


def run_tray(stop_event: threading.Event, on_quit: Callable) -> None:
    def _quit(icon, item):
        stop_event.set()
        icon.stop()
        on_quit()

    icon = pystray.Icon(
        name="VdiskUploader",
        icon=_create_icon_image(),
        title="Vdisk Uploader",
        menu=pystray.Menu(
            pystray.MenuItem("Vdisk Uploader 실행 중", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", _quit),
        )
    )
    icon.run()
