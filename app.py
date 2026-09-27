import os
import queue
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import customtkinter as ctk
from PIL import Image, ImageDraw

from core import devices
from core.applog import log_file, setup
from core.encoder import AudioEncoder
from core.ffmpeg_bin import assets_dir, find_ffmpeg
from core.server import StreamServer

try:
    import qrcode
    HAVE_QRCODE = True
except ImportError:
    HAVE_QRCODE = False

# ==============================================================================
# Modern Color Palette & Design Tokens
# ==============================================================================
BG_DARK = "#0b0f19"             # Sleek dark window background
CARD_BG = "#1e293b"             # Slate 800 card background
CARD_BORDER = "#334155"         # Slate 700 fine border
INPUT_BG = "#0f172a"            # Slate 900 input fields
INPUT_BORDER = "#334155"        # Slate 700 input borders

DISABLED_BG = "#141c2e"         # Dimmed background for disabled inputs
DISABLED_BORDER = "#1e293b"     # Dimmed border for disabled inputs
DISABLED_TEXT = "#64748b"       # Muted text for disabled inputs

BUTTON_SECONDARY = "#334155"    # Slate 700 action button
BUTTON_SECONDARY_HOVER = "#475569"

PRIMARY_BLUE = "#2563eb"        # Vibrant Blue 600
PRIMARY_HOVER = "#1d4ed8"       # Blue 700

STOP_RED = "#ef4444"            # Vibrant Red 500
STOP_HOVER = "#dc2626"          # Red 600

LIVE_GREEN = "#10b981"          # Emerald 500
LIVE_BG = "#064e3b"             # Dark Emerald pill background
LIVE_BORDER = "#059669"

STOP_BG = "#1e293b"
STOP_BORDER = "#475569"

TEXT_PRIMARY = "#f8fafc"        # Slate 50 (brightest)
TEXT_SECONDARY = "#94a3b8"      # Slate 400 (secondary)
TEXT_MUTED = "#64748b"          # Slate 500 (hints and footer)
TEXT_AMBER = "#f59e0b"          # Amber 500 (warning)

BITRATES = ["96k", "128k", "160k", "192k", "256k"]
SAMPLERATES = [22050, 32000, 44100, 48000]
CHANNELS = {"original": "Original", "mono": "Mono", "stereo": "Estéreo"}
BUFFERS = [1, 2, 4, 8, 16, 32]
EMPTY = ("", "Sin dispositivos", "Buscando dispositivos...")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# ==============================================================================
# Vector Icon Generator (4x Supersampled Anti-Aliased Icons)
# ==============================================================================
def create_app_icons() -> dict[str, ctk.CTkImage]:
    """Generates crisp, perfectly aligned vector icons using Pillow."""
    scale = 4

    def canvas(w: int, h: int):
        return Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0)), w * scale, h * scale

    def finish(img: Image.Image, w: int, h: int) -> ctk.CTkImage:
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        return ctk.CTkImage(light_image=resized, dark_image=resized, size=(w, h))

    color_light = (203, 213, 225, 255)  # #cbd5e1 (Slate 300)
    color_white = (255, 255, 255, 255)  # Pure White
    color_sky = (56, 189, 248, 255)     # #38bdf8 (Sky 400)
    color_green = (52, 211, 153, 255)   # #34d399 (Emerald 400)
    color_muted = (148, 163, 184, 255)  # #94a3b8 (Slate 400)

    # 1. Header Broadcast Icon (22x22)
    img, w, h = canvas(22, 22)
    d = ImageDraw.Draw(img)
    d.ellipse([9 * scale, 9 * scale, 13 * scale, 13 * scale], fill=color_sky)
    d.arc([5 * scale, 5 * scale, 17 * scale, 17 * scale], start=210, end=330, fill=color_sky, width=round(1.8 * scale))
    d.arc([5 * scale, 5 * scale, 17 * scale, 17 * scale], start=30, end=150, fill=color_sky, width=round(1.8 * scale))
    d.arc([1 * scale, 1 * scale, 21 * scale, 21 * scale], start=215, end=325, fill=color_sky, width=round(1.8 * scale))
    d.arc([1 * scale, 1 * scale, 21 * scale, 21 * scale], start=35, end=145, fill=color_sky, width=round(1.8 * scale))
    icon_header = finish(img, 22, 22)

    # 2. Refresh Sync Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.arc([2 * scale, 2 * scale, 12 * scale, 12 * scale], start=35, end=305, fill=color_light, width=round(1.6 * scale))
    d.polygon([(11 * scale, 0 * scale), (13.5 * scale, 4.2 * scale), (8.5 * scale, 4.2 * scale)], fill=color_light)
    icon_refresh = finish(img, 14, 14)

    # 3. Audio Test / Speaker Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.polygon([
        (2 * scale, 5 * scale),
        (5 * scale, 5 * scale),
        (8 * scale, 2 * scale),
        (8 * scale, 12 * scale),
        (5 * scale, 9 * scale),
        (2 * scale, 9 * scale),
    ], fill=color_light)
    d.arc([7 * scale, 4 * scale, 12 * scale, 10 * scale], start=-60, end=60, fill=color_light, width=round(1.5 * scale))
    icon_test = finish(img, 14, 14)

    # 4. Copy Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4 * scale, 1 * scale, 12 * scale, 9 * scale], radius=round(1.2 * scale), outline=color_light, width=round(1.3 * scale))
    d.rounded_rectangle([2 * scale, 4 * scale, 10 * scale, 13 * scale], radius=round(1.2 * scale), outline=color_light, width=round(1.3 * scale), fill=(30, 41, 59, 255))
    icon_copy = finish(img, 14, 14)

    # 5. Checkmark Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.line([(3 * scale, 7 * scale), (6 * scale, 10.5 * scale)], fill=color_green, width=round(2 * scale))
    d.line([(6 * scale, 10.5 * scale), (11.5 * scale, 3.5 * scale)], fill=color_green, width=round(2 * scale))
    icon_check = finish(img, 14, 14)

    # 6. External Link Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.line([(2 * scale, 6 * scale), (2 * scale, 12 * scale), (9 * scale, 12 * scale), (9 * scale, 8 * scale)], fill=color_light, width=round(1.3 * scale))
    d.line([(5 * scale, 9 * scale), (12 * scale, 2 * scale)], fill=color_light, width=round(1.4 * scale))
    d.line([(8 * scale, 2 * scale), (12 * scale, 2 * scale), (12 * scale, 6 * scale)], fill=color_light, width=round(1.4 * scale))
    icon_open = finish(img, 14, 14)

    # 7. Play Triangle Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.polygon([(4 * scale, 2.5 * scale), (12 * scale, 7 * scale), (4 * scale, 11.5 * scale)], fill=color_white)
    icon_play = finish(img, 14, 14)

    # 8. Stop Square Icon (14x14)
    img, w, h = canvas(14, 14)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([3 * scale, 3 * scale, 11 * scale, 11 * scale], radius=round(1.5 * scale), fill=color_white)
    icon_stop = finish(img, 14, 14)

    # 9. Log Document Icon (12x12)
    img, w, h = canvas(12, 12)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * scale, 1 * scale, 10 * scale, 11 * scale], radius=round(1 * scale), outline=color_muted, width=round(1.2 * scale))
    d.line([(4 * scale, 4 * scale), (8 * scale, 4 * scale)], fill=color_muted, width=round(1 * scale))
    d.line([(4 * scale, 6.5 * scale), (8 * scale, 6.5 * scale)], fill=color_muted, width=round(1 * scale))
    d.line([(4 * scale, 9 * scale), (6.5 * scale, 9 * scale)], fill=color_muted, width=round(1 * scale))
    icon_log = finish(img, 12, 12)

    return {
        "header": icon_header,
        "refresh": icon_refresh,
        "test": icon_test,
        "copy": icon_copy,
        "check": icon_check,
        "open": icon_open,
        "play": icon_play,
        "stop": icon_stop,
        "log": icon_log,
    }


def local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def lan_reachable(ip: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.log = setup()
        self.title("Transmisor de Audio LAN")
        self.geometry("980x640")
        self.minsize(940, 600)
        self.configure(fg_color=BG_DARK)

        self.server = None
        self.encoder = None
        self.running = False
        self.started_at = 0.0
        self.lan_ip = local_ip()
        self._ui_queue: queue.Queue = queue.Queue()
        self._state_lock = threading.Lock()
        self._state = {"device": "", "bitrate": "", "samplerate": 0, "kbps": 0.0, "url": ""}
        self._ffmpeg_drawer_visible = False

        self.icons = create_app_icons()

        self._build_ui()
        self._load_ffmpeg()
        self._refresh_devices(silent=True)
        self._update_qr(self._url(9000))

        self.log.info(
            "Inicio. ffmpeg=%s ip=%s pantalla=%sx%s",
            self.entry_ffmpeg.get() or "no encontrado",
            self.lan_ip,
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._drain)
        self.after(500, self._tick)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---------------- 1. Top Header Bar ----------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        # Left Title Block
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        title_row = ctk.CTkFrame(title_box, fg_color="transparent")
        title_row.pack(anchor="w")

        icon_badge = ctk.CTkLabel(
            title_row,
            text="",
            image=self.icons["header"],
            width=36,
            height=36,
            fg_color="#1e293b",
            corner_radius=8,
        )
        icon_badge.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            title_row,
            text="Transmisor de Audio LAN",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Transmití cualquier entrada de audio de tu PC a celulares, tablets y Smart TVs en tu red local",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 0))

        # Right Status / Config Pill
        ffmpeg_box = ctk.CTkFrame(header, fg_color="transparent")
        ffmpeg_box.grid(row=0, column=2, sticky="e")

        self.btn_ffmpeg_badge = ctk.CTkButton(
            ffmpeg_box,
            text="● FFmpeg listo",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=28,
            corner_radius=14,
            fg_color=LIVE_BG,
            hover_color="#065f46",
            text_color="#34d399",
            border_width=1,
            border_color=LIVE_BORDER,
            command=self._toggle_ffmpeg_drawer,
        )
        self.btn_ffmpeg_badge.pack(side="right")

        # ---------------- 1.1 Collapsible FFmpeg Drawer ----------------
        self.ffmpeg_drawer = ctk.CTkFrame(
            self,
            fg_color=CARD_BG,
            corner_radius=10,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.ffmpeg_drawer.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.ffmpeg_drawer,
            text="Ruta ffmpeg.exe:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, padx=(14, 8), pady=10, sticky="w")

        self.entry_ffmpeg = ctk.CTkEntry(
            self.ffmpeg_drawer,
            height=32,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=12),
        )
        self.entry_ffmpeg.grid(row=0, column=1, sticky="ew", pady=10)

        self.btn_browse = ctk.CTkButton(
            self.ffmpeg_drawer,
            text="Examinar...",
            width=90,
            height=32,
            fg_color=BUTTON_SECONDARY,
            hover_color=BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._browse_ffmpeg,
        )
        self.btn_browse.grid(row=0, column=2, padx=(8, 14), pady=10)

        self.lbl_binary_hint = ctk.CTkLabel(
            self.ffmpeg_drawer,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_binary_hint.grid(row=1, column=0, columnspan=3, padx=14, pady=(0, 8), sticky="w")

        # ---------------- 2. Main Two-Column Body ----------------
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(6, 10))
        body.grid_columnconfigure(0, weight=1, uniform="body_col")
        body.grid_columnconfigure(1, weight=1, uniform="body_col")
        body.grid_rowconfigure(0, weight=1)

        # ========================================================
        # LEFT COLUMN: Fuente de Audio & Ajustes
        # ========================================================
        left_col = ctk.CTkFrame(body, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_col.grid_columnconfigure(0, weight=1)
        left_col.grid_rowconfigure(0, weight=1)

        card_left = ctk.CTkFrame(
            left_col,
            fg_color=CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card_left.grid(row=0, column=0, sticky="nsew")
        card_left.grid_columnconfigure(0, weight=1)
        card_left.grid_columnconfigure(1, weight=1)

        # Section Title: Clean typography
        ctk.CTkLabel(
            card_left,
            text="Entrada de Audio",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 10))

        # Device Combo
        self.device_combo = ctk.CTkComboBox(
            card_left,
            height=36,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            button_color=BUTTON_SECONDARY,
            button_hover_color=BUTTON_SECONDARY_HOVER,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=BUTTON_SECONDARY,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            values=["Buscando dispositivos..."],
        )
        self.device_combo.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 8))

        # Device Actions Row
        dev_action_row = ctk.CTkFrame(card_left, fg_color="transparent")
        dev_action_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 14))

        self.btn_refresh = ctk.CTkButton(
            dev_action_row,
            text=" Actualizar",
            image=self.icons["refresh"],
            compound="left",
            width=100,
            height=30,
            fg_color=BUTTON_SECONDARY,
            hover_color=BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._refresh_devices(silent=False),
        )
        self.btn_refresh.pack(side="left")

        self.btn_test = ctk.CTkButton(
            dev_action_row,
            text=" Probar entrada",
            image=self.icons["test"],
            compound="left",
            width=120,
            height=30,
            fg_color=BUTTON_SECONDARY,
            hover_color=BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._test_device,
        )
        self.btn_test.pack(side="left", padx=(8, 0))

        self.lbl_device_hint = ctk.CTkLabel(
            dev_action_row,
            text="",
            text_color=TEXT_SECONDARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="w",
        )
        self.lbl_device_hint.pack(side="left", padx=(10, 0), fill="x", expand=True)

        # Subtle Separator
        sep = ctk.CTkFrame(card_left, height=1, fg_color=CARD_BORDER)
        sep.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 12))

        # Settings Title: Clean typography
        ctk.CTkLabel(
            card_left,
            text="Parámetros de Transmisión",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 8))

        # Form Controls Grid: Row 5: Puerto (Left Aligned!) & Bitrate
        f_port = ctk.CTkFrame(card_left, fg_color="transparent")
        f_port.grid(row=5, column=0, sticky="ew", padx=(20, 8), pady=(0, 8))
        ctk.CTkLabel(f_port, text="Puerto de red", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.field_port = ctk.CTkEntry(
            f_port,
            height=32,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            justify="left",
            font=ctk.CTkFont(size=12),
        )
        self.field_port.insert(0, "9000")
        self.field_port.pack(fill="x", pady=(2, 0))

        f_bitrate = ctk.CTkFrame(card_left, fg_color="transparent")
        f_bitrate.grid(row=5, column=1, sticky="ew", padx=(8, 20), pady=(0, 8))
        ctk.CTkLabel(f_bitrate, text="Calidad / Bitrate", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.field_bitrate = ctk.CTkComboBox(
            f_bitrate,
            height=32,
            values=BITRATES,
            state="readonly",
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            button_color=BUTTON_SECONDARY,
            button_hover_color=BUTTON_SECONDARY_HOVER,
            dropdown_fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.field_bitrate.set("128k")
        self.field_bitrate.pack(fill="x", pady=(2, 0))

        # Row 6: Sample Rate & Canales
        f_rate = ctk.CTkFrame(card_left, fg_color="transparent")
        f_rate.grid(row=6, column=0, sticky="ew", padx=(20, 8), pady=(0, 8))
        ctk.CTkLabel(f_rate, text="Frecuencia (Sample rate)", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.field_rate = ctk.CTkComboBox(
            f_rate,
            height=32,
            values=[str(v) for v in SAMPLERATES],
            state="readonly",
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            button_color=BUTTON_SECONDARY,
            button_hover_color=BUTTON_SECONDARY_HOVER,
            dropdown_fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.field_rate.set("44100")
        self.field_rate.pack(fill="x", pady=(2, 0))

        f_channels = ctk.CTkFrame(card_left, fg_color="transparent")
        f_channels.grid(row=6, column=1, sticky="ew", padx=(8, 20), pady=(0, 8))
        ctk.CTkLabel(f_channels, text="Canales de audio", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.field_channels = ctk.CTkComboBox(
            f_channels,
            height=32,
            values=list(CHANNELS.values()),
            state="readonly",
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            button_color=BUTTON_SECONDARY,
            button_hover_color=BUTTON_SECONDARY_HOVER,
            dropdown_fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.field_channels.set(CHANNELS["original"])
        self.field_channels.pack(fill="x", pady=(2, 0))

        # Row 7: Buffer & Low Latency Checkbox (clean text without misaligned emoji)
        f_buffer = ctk.CTkFrame(card_left, fg_color="transparent")
        f_buffer.grid(row=7, column=0, sticky="ew", padx=(20, 8), pady=(0, 10))
        ctk.CTkLabel(f_buffer, text="Buffer de captura (MB)", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.field_buffer = ctk.CTkComboBox(
            f_buffer,
            height=32,
            values=[str(v) for v in BUFFERS],
            state="readonly",
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            button_color=BUTTON_SECONDARY,
            button_hover_color=BUTTON_SECONDARY_HOVER,
            dropdown_fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.field_buffer.set("4")
        self.field_buffer.pack(fill="x", pady=(2, 0))

        f_nobuf = ctk.CTkFrame(card_left, fg_color="transparent")
        f_nobuf.grid(row=7, column=1, sticky="ew", padx=(8, 20), pady=(0, 10))
        ctk.CTkLabel(f_nobuf, text="Modo de latencia", text_color=TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(anchor="w")
        self.chk_nobuffer = ctk.CTkCheckBox(
            f_nobuf,
            text="Baja latencia (sin buffer)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_PRIMARY,
            fg_color=PRIMARY_BLUE,
            hover_color=PRIMARY_HOVER,
        )
        self.chk_nobuffer.select()
        self.chk_nobuffer.pack(anchor="w", pady=(8, 0))

        # Big Hero CTA Button at Bottom of Left Column
        self.btn_toggle = ctk.CTkButton(
            left_col,
            text=" Iniciar transmisión",
            image=self.icons["play"],
            compound="left",
            height=48,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            fg_color=PRIMARY_BLUE,
            hover_color=PRIMARY_HOVER,
            command=self._toggle,
        )
        self.btn_toggle.grid(row=1, column=0, sticky="ew", pady=(12, 0))

        # ========================================================
        # RIGHT COLUMN: Estado, Métricas & Conexión Móvil
        # ========================================================
        right_col = ctk.CTkFrame(body, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_rowconfigure(1, weight=1)

        # Card: Estado y URL
        self.card_status = ctk.CTkFrame(
            right_col,
            fg_color=CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.card_status.grid(row=0, column=0, sticky="ew")
        self.card_status.grid_columnconfigure(0, weight=1)

        # Header of Status Card
        status_header = ctk.CTkFrame(self.card_status, fg_color="transparent")
        status_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        status_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            status_header,
            text="Estado de la Transmisión",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")

        self.lbl_state = ctk.CTkLabel(
            status_header,
            text="○ DETENIDO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_SECONDARY,
            fg_color=STOP_BG,
            corner_radius=12,
            padx=12,
            pady=3,
        )
        self.lbl_state.grid(row=0, column=1, sticky="e")

        # URL Box Row
        url_container = ctk.CTkFrame(self.card_status, fg_color="transparent")
        url_container.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        url_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            url_container,
            text="Dirección de escucha (URL):",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        self.entry_url = ctk.CTkEntry(
            url_container,
            height=34,
            fg_color=INPUT_BG,
            border_color=INPUT_BORDER,
            text_color="#38bdf8",
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.entry_url.grid(row=1, column=0, sticky="ew")

        self.btn_copy = ctk.CTkButton(
            url_container,
            text=" Copiar",
            image=self.icons["copy"],
            compound="left",
            width=88,
            height=34,
            fg_color=BUTTON_SECONDARY,
            hover_color=BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._copy_url,
        )
        self.btn_copy.grid(row=1, column=1, padx=(8, 0))

        self.btn_open = ctk.CTkButton(
            url_container,
            text=" Abrir",
            image=self.icons["open"],
            compound="left",
            width=80,
            height=34,
            fg_color=BUTTON_SECONDARY,
            hover_color=BUTTON_SECONDARY_HOVER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._open_browser,
        )
        self.btn_open.grid(row=1, column=2, padx=(6, 0))
        self._set_url(f"http://{self.lan_ip}:9000")

        # Firewall Warning Container (Hidden by default)
        self.firewall_frame = ctk.CTkFrame(
            self.card_status,
            fg_color="#2d1b09",
            corner_radius=8,
            border_width=1,
            border_color="#78350f",
        )
        self.lbl_firewall = ctk.CTkLabel(
            self.firewall_frame,
            text="",
            text_color=TEXT_AMBER,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.lbl_firewall.pack(padx=12, pady=8, fill="x")

        # Metrics Row (3 sleek modern cards without hollow emojis)
        self.metrics = ctk.CTkFrame(self.card_status, fg_color="transparent")
        self.metrics.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 16))
        for col in range(3):
            self.metrics.grid_columnconfigure(col, weight=1, uniform="metric_tile")

        self.metric_labels = {}
        metric_configs = [
            ("clients", "Oyentes conectados"),
            ("kbps", "Tasa de datos"),
            ("uptime", "Tiempo activo"),
        ]

        for idx, (key, caption) in enumerate(metric_configs):
            pad_left = 0 if idx == 0 else 6
            pad_right = 0 if idx == 2 else 6
            tile = ctk.CTkFrame(
                self.metrics,
                fg_color=INPUT_BG,
                corner_radius=10,
                border_width=1,
                border_color=INPUT_BORDER,
            )
            tile.grid(row=0, column=idx, sticky="ew", padx=(pad_left, pad_right))
            tile.grid_columnconfigure(0, weight=1)

            val_label = ctk.CTkLabel(
                tile,
                text="0" if key == "clients" else ("0 kbps" if key == "kbps" else "00:00"),
                font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                text_color=TEXT_PRIMARY,
            )
            val_label.grid(row=0, column=0, pady=(10, 0))

            lbl_sub = ctk.CTkLabel(
                tile,
                text=caption,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=TEXT_SECONDARY,
            )
            lbl_sub.grid(row=1, column=0, pady=(2, 10))

            self.metric_labels[key] = val_label

        # Card: Conexión Rápida & QR
        self.card_connect = ctk.CTkFrame(
            right_col,
            fg_color=CARD_BG,
            corner_radius=12,
            border_width=1,
            border_color=CARD_BORDER,
        )
        self.card_connect.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.card_connect.grid_columnconfigure(1, weight=1)
        self.card_connect.grid_rowconfigure(0, weight=1)

        # White Rounded QR Container (High contrast, modern framing)
        self.qr_container = ctk.CTkFrame(
            self.card_connect,
            fg_color="#ffffff",
            corner_radius=12,
            width=136,
            height=136,
        )
        self.qr_container.grid(row=0, column=0, padx=18, pady=16, sticky="nw")
        self.qr_container.grid_propagate(False)

        self.lbl_qr = ctk.CTkLabel(
            self.qr_container,
            text="",
            text_color="#1e293b",
            font=ctk.CTkFont(family="Segoe UI", size=10),
        )
        self.lbl_qr.place(relx=0.5, rely=0.5, anchor="center")

        # Instructions beside QR
        inst_box = ctk.CTkFrame(self.card_connect, fg_color="transparent")
        inst_box.grid(row=0, column=1, sticky="nsew", padx=(6, 18), pady=16)

        ctk.CTkLabel(
            inst_box,
            text="Conectar celulares y Smart TVs",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            inst_box,
            text="Escaneá el código QR con la cámara de tu teléfono o tablet para escuchar de inmediato sin instalar programas.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY,
            wraplength=250,
            justify="left",
        ).pack(anchor="w", pady=(6, 6))

        ctk.CTkLabel(
            inst_box,
            text="✓ Compatible con Chrome, Safari, Firefox y reproductores VLC (/stream.mp3).",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED,
            wraplength=250,
            justify="left",
        ).pack(anchor="w")

        # ---------------- 3. Bottom Status Bar ----------------
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent", height=24)
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=24, pady=(6, 12))
        bottom_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bottom_bar,
            text="Transmisor de Audio LAN • Streaming HTTP MP3",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")

        self.lbl_toast = ctk.CTkLabel(
            bottom_bar,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=LIVE_GREEN,
        )
        self.lbl_toast.grid(row=0, column=1, sticky="e", padx=(0, 16))

        btn_log = ctk.CTkButton(
            bottom_bar,
            text=" Ver archivo de log",
            image=self.icons["log"],
            compound="left",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=22,
            fg_color="transparent",
            hover_color=BUTTON_SECONDARY,
            text_color=TEXT_SECONDARY,
            command=self._open_log,
        )
        btn_log.grid(row=0, column=2, sticky="e")

    def _toggle_ffmpeg_drawer(self) -> None:
        if self._ffmpeg_drawer_visible:
            self.ffmpeg_drawer.grid_forget()
            self._ffmpeg_drawer_visible = False
        else:
            self.ffmpeg_drawer.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
            self._ffmpeg_drawer_visible = True

    def _open_log(self) -> None:
        path = log_file()
        try:
            if path.exists():
                os.startfile(str(path))
            else:
                self._toast("El archivo de log aún no fue creado.")
        except Exception as exc:
            self._toast(f"No se pudo abrir el log: {exc}", is_error=True)

    def _load_ffmpeg(self) -> None:
        found = find_ffmpeg()
        self.entry_ffmpeg.delete(0, "end")
        self.entry_ffmpeg.insert(0, found or "")
        if found:
            self.btn_ffmpeg_badge.configure(
                text="● FFmpeg listo",
                fg_color=LIVE_BG,
                border_color=LIVE_BORDER,
                text_color="#34d399",
            )
            self.lbl_binary_hint.configure(
                text=f"Ruta activa: {found}",
                text_color=LIVE_GREEN,
            )
        else:
            self.btn_ffmpeg_badge.configure(
                text="⚠ FFmpeg requerido",
                fg_color="#450a0a",
                border_color="#b91c1c",
                text_color="#f87171",
            )
            self.lbl_binary_hint.configure(
                text="No se encontró ffmpeg.exe. Bajalo de gyan.dev/ffmpeg/builds y dejalo junto al programa.",
                text_color=STOP_RED,
            )
            if not self._ffmpeg_drawer_visible:
                self._toggle_ffmpeg_drawer()

    def _browse_ffmpeg(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askopenfilename(
            title="Elegir ffmpeg.exe",
            filetypes=[("ffmpeg", "ffmpeg.exe"), ("Todos", "*.*")],
        )
        if chosen:
            self.entry_ffmpeg.delete(0, "end")
            self.entry_ffmpeg.insert(0, chosen)
            self.btn_ffmpeg_badge.configure(
                text="● FFmpeg listo",
                fg_color=LIVE_BG,
                border_color=LIVE_BORDER,
                text_color="#34d399",
            )
            self.lbl_binary_hint.configure(text=f"Ruta activa: {chosen}", text_color=LIVE_GREEN)

    def _refresh_devices(self, silent: bool = False) -> None:
        ffmpeg = self.entry_ffmpeg.get().strip()
        if not ffmpeg:
            if not silent:
                self.lbl_device_hint.configure(text="● Indicá la ruta de ffmpeg primero", text_color=STOP_RED)
            return
        self.btn_refresh.configure(state="disabled", text=" Buscando...")
        self.lbl_device_hint.configure(text="● Buscando entradas...", text_color=TEXT_MUTED)

        def worker() -> None:
            try:
                found, error = devices.list_inputs(ffmpeg), None
            except devices.DeviceError as exc:
                found, error = [], str(exc)
            self._post(lambda: self._apply_devices(found, error, silent))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_devices(self, found: list[str], error: str | None, silent: bool) -> None:
        self.btn_refresh.configure(state="normal", text=" Actualizar")
        if error:
            self.device_combo.configure(values=["Sin dispositivos"])
            self.device_combo.set("Sin dispositivos")
            self.lbl_device_hint.configure(text="● " + error, text_color=STOP_RED)
            return
        if not found:
            self.device_combo.configure(values=["Sin dispositivos"])
            self.device_combo.set("Sin dispositivos")
            self.lbl_device_hint.configure(text="● Sin entradas de audio detectadas", text_color=TEXT_AMBER)
            return
        current = self.device_combo.get()
        self.device_combo.configure(values=found)
        self.device_combo.set(current if current in found else found[0])
        self.lbl_device_hint.configure(text=f"● {len(found)} entrada(s) disponible(s)", text_color=LIVE_GREEN)
        self.log.info("Entradas: %s", " | ".join(found))
        if not silent:
            self._test_device()

    def _test_device(self) -> None:
        ffmpeg = self.entry_ffmpeg.get().strip()
        device = self.device_combo.get().strip()
        if not ffmpeg or device in EMPTY:
            self.lbl_device_hint.configure(text="● Elegí una entrada primero", text_color=STOP_RED)
            return
        self.btn_test.configure(state="disabled", text=" Probando...")

        def worker() -> None:
            ok, message = devices.test_input(ffmpeg, device)
            self._post(lambda: self._apply_test(ok, message))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_test(self, ok: bool, message: str) -> None:
        self.btn_test.configure(state="normal", text=" Probar entrada")
        self.lbl_device_hint.configure(text=f"● {message}", text_color=LIVE_GREEN if ok else STOP_RED)
        self.log.info("Prueba del dispositivo ok=%s: %s", ok, message)

    def _current_port(self) -> int:
        return int(self.field_port.get().strip() or 0)

    def _url(self, port: int | None = None) -> str:
        return f"http://{self.lan_ip}:{port or self._current_port()}"

    def _set_url(self, url: str) -> None:
        self.entry_url.configure(state="normal")
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, url)
        self.entry_url.configure(state="readonly")

    def _toggle(self) -> None:
        self._stop() if self.running else self._start()

    def _start(self) -> None:
        ffmpeg = self.entry_ffmpeg.get().strip()
        device = self.device_combo.get().strip()
        if not ffmpeg or not Path(ffmpeg).is_file():
            self._fail("No se encontró ffmpeg.exe en la ruta indicada.")
            return
        if not device or device in EMPTY:
            self._fail("Elegí una entrada de audio válida.")
            return
        try:
            port = self._current_port()
        except ValueError:
            self._fail("El puerto debe ser un número entero.")
            return
        if not 1024 < port < 65536:
            self._fail("El puerto debe estar entre 1025 y 65535.")
            return

        channel_label = self.field_channels.get()
        channel_key = next((key for key, label in CHANNELS.items() if label == channel_label), "original")
        samplerate = int(self.field_rate.get())
        bitrate = self.field_bitrate.get()

        server = StreamServer("0.0.0.0", port, assets_dir(), status_provider=self._status_payload)
        try:
            server.start()
        except OSError as exc:
            self._fail(f"No se pudo abrir el puerto {port}: {exc.strerror or exc}")
            return

        encoder = AudioEncoder(
            ffmpeg=ffmpeg,
            device=device,
            bitrate=bitrate,
            samplerate=samplerate,
            channels=channel_key,
            rtbufsize_mb=int(self.field_buffer.get()),
            nobuffer=bool(self.chk_nobuffer.get()),
            on_audio=server.broadcast,
            on_error=lambda message: self._post(lambda: self._fail(message)),
            on_finished=lambda code: self._post(lambda: self._encoder_stopped(code)),
        )
        encoder.start()

        self.server, self.encoder, self.running = server, encoder, True
        self.started_at = time.time()
        with self._state_lock:
            self._state.update(
                device=device, bitrate=bitrate, samplerate=samplerate, kbps=0.0, url=self._url(port)
            )
        self.log.info(
            "Emitiendo '%s' en %s (%s, %d Hz, buffer %s MB)",
            device,
            self._url(port),
            bitrate,
            samplerate,
            self.field_buffer.get(),
        )

        self._set_url(self._url(port))
        self._set_controls(True)
        self.btn_toggle.configure(
            text=" Detener transmisión",
            image=self.icons["stop"],
            fg_color=STOP_RED,
            hover_color=STOP_HOVER,
        )
        self.lbl_state.configure(
            text="● EN VIVO",
            text_color="#34d399",
            fg_color=LIVE_BG,
        )
        self.firewall_frame.grid_forget()
        self._toast("Transmisión iniciada correctamente")
        self._update_qr(self._url(port))
        threading.Thread(target=self._check_firewall, args=(port,), daemon=True).start()

    def _check_firewall(self, port: int) -> None:
        time.sleep(1.0)
        ok = lan_reachable(self.lan_ip, port)
        self._post(lambda: self._apply_firewall(ok, port))

    def _apply_firewall(self, ok: bool, port: int) -> None:
        if not self.running:
            return
        if not ok:
            self.lbl_firewall.configure(
                text=f"⚠ El firewall de Windows podría bloquear el puerto {port}.\n"
                     f"Si no podés conectarte desde otro dispositivo, ejecutá en PowerShell como Administrador:\n"
                     f'New-NetFirewallRule -DisplayName "Audio LAN" -Direction Inbound -LocalPort {port} -Protocol TCP -Action Allow -Profile Private'
            )
            self.firewall_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

    def _encoder_stopped(self, code: int) -> None:
        if not self.running:
            return
        if code not in (0, 255, -1):
            self._fail(f"ffmpeg se detuvo inesperadamente (código {code}). Revisá el log.")
        else:
            self._stop()

    def _fail(self, message: str) -> None:
        self.log.error(message)
        if self.running:
            self._stop()
        self.lbl_state.configure(text="✕ ERROR", text_color="#f87171", fg_color="#450a0a")
        self._toast(f"Error: {message}", is_error=True)

    def _stop(self) -> None:
        if self.encoder:
            self.encoder.stop()
            self.encoder = None
        if self.server:
            self.server.stop()
            self.server = None
        self.running = False
        self.started_at = 0.0
        self._set_controls(False)
        self.btn_toggle.configure(
            text=" Iniciar transmisión",
            image=self.icons["play"],
            fg_color=PRIMARY_BLUE,
            hover_color=PRIMARY_HOVER,
        )
        if self.lbl_state.cget("text") != "✕ ERROR":
            self.lbl_state.configure(text="○ DETENIDO", text_color=TEXT_SECONDARY, fg_color=STOP_BG)
        self.firewall_frame.grid_forget()
        self.metric_labels["clients"].configure(text="0")
        self.metric_labels["kbps"].configure(text="0 kbps")
        self.metric_labels["uptime"].configure(text="00:00")
        with self._state_lock:
            self._state.update(kbps=0.0)
        self.log.info("Transmisión detenida")

    def _set_controls(self, locked: bool) -> None:
        # Device combo
        self.device_combo.configure(state="disabled" if locked else "normal")
        self.entry_ffmpeg.configure(state="disabled" if locked else "normal")

        # Port entry: explicitly style as disabled when locked!
        if locked:
            self.field_port.configure(
                state="disabled",
                fg_color=DISABLED_BG,
                border_color=DISABLED_BORDER,
                text_color=DISABLED_TEXT,
            )
        else:
            self.field_port.configure(
                state="normal",
                fg_color=INPUT_BG,
                border_color=INPUT_BORDER,
                text_color=TEXT_PRIMARY,
            )

        # Combos and buttons
        for combo in (self.field_bitrate, self.field_rate, self.field_channels, self.field_buffer):
            combo.configure(state="disabled" if locked else "readonly")
        for button in (self.btn_refresh, self.btn_test, self.btn_browse):
            button.configure(state="disabled" if locked else "normal")
        self.chk_nobuffer.configure(state="disabled" if locked else "normal")

    def _status_payload(self) -> dict:
        with self._state_lock:
            payload = dict(self._state)
        payload["kbps"] = round(self.encoder.kbps, 1) if (self.encoder and self.encoder.running) else 0.0
        return payload

    def _tick(self) -> None:
        clients = self.server.client_count() if self.server else 0
        kbps = self.encoder.kbps if (self.encoder and self.encoder.running) else 0.0
        elapsed = int(time.time() - self.started_at) if self.started_at else 0
        self.metric_labels["clients"].configure(text=str(clients))
        self.metric_labels["kbps"].configure(text=f"{kbps:.0f} kbps" if kbps else "0 kbps")
        self.metric_labels["uptime"].configure(
            text=f"{elapsed // 60:02d}:{elapsed % 60:02d}" if elapsed else "00:00"
        )
        with self._state_lock:
            self._state.update(kbps=round(kbps, 1))
        self.after(500, self._tick)

    def _toast(self, message: str, is_error: bool = False) -> None:
        self.lbl_toast.configure(
            text=message,
            text_color=STOP_RED if is_error else LIVE_GREEN,
        )
        self.after(6000, lambda: self.lbl_toast.configure(text=""))

    def _update_qr(self, url: str) -> None:
        if not HAVE_QRCODE:
            self.lbl_qr.configure(text="QR no disponible")
            return
        try:
            code = qrcode.QRCode(border=1)
            code.add_data(url)
            code.make(fit=True)
            image = code.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGB")
            self.lbl_qr.configure(
                text="",
                image=ctk.CTkImage(light_image=image, dark_image=image, size=(120, 120)),
            )
        except Exception as exc:
            self.log.warning("No se pudo generar el QR: %s", exc)
            self.lbl_qr.configure(text="Error al generar QR")

    def _copy_url(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.entry_url.get())
        self.btn_copy.configure(text=" Copiado", image=self.icons["check"], fg_color=LIVE_BG)
        self._toast("URL copiada al portapapeles")
        self.after(
            1800,
            lambda: self.btn_copy.configure(text=" Copiar", image=self.icons["copy"], fg_color=BUTTON_SECONDARY),
        )

    def _open_browser(self) -> None:
        webbrowser.open(self.entry_url.get())

    def _post(self, action) -> None:
        self._ui_queue.put(action)

    def _drain(self) -> None:
        while True:
            try:
                action = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except Exception as exc:
                self.log.exception("Error en la interfaz: %s", exc)
        self.after(80, self._drain)

    def _on_close(self) -> None:
        if self.running:
            self._stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
