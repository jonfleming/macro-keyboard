#!/usr/bin/env python3
"""Visual editor for the macro keypad text file.

The window is a picture of the keypad. Each key and each knob action edits
the same `{brace}` text that macros.txt already uses.
"""

from __future__ import annotations

import argparse
import ctypes
import math
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

import yaml

from converter import DEFAULT_TXT, DEFAULT_YAML, cmd_to_yaml, find_keyboard_tool
from macro_parser import (
    KNOB_ACTIONS,
    MODIFIER_ALIASES,
    Knob,
    Mapping,
    empty_layer,
    load_yaml_mapping,
    macro_to_text,
    mapping_to_text,
    text_to_macro,
    text_to_mapping,
)

BG = "#0e1013"
PANEL = "#171a20"
RAISED = "#222733"
TEXT = "#e8eaef"
DIM = "#8e96a3"
FAINT = "#6d7582"
ACCENT = "#79e3ff"
ACCENT_INK = "#062026"
ACCENT_BG = "#143941"
DANGER = "#ff8d9a"
OK = "#8ee0a8"
WARN = "#e6b15c"
CHASSIS = "#14171c"
KEYCAP = "#1b1e25"
SILVER = "#aeb6be"
SILVER_EDGE = "#8b939b"
KNOB_FACE = "#121417"
LINE = "#2c313b"

FONT = "Segoe UI"
MONO = "Consolas"

CANON_MOD = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "win": "Win",
    "rctrl": "Right Ctrl",
    "rshift": "Right Shift",
    "ralt": "Right Alt",
    "rwin": "Right Win",
}

KEY_WORDS = {
    "enter": "↵",
    "return": "↵",
    "tab": "⇥",
    "backspace": "⌫",
    "escape": "Esc",
    "esc": "Esc",
    "delete": "Del",
    "del": "Del",
    "insert": "Ins",
    "ins": "Ins",
    "space": "Space",
    "home": "Home",
    "end": "End",
    "pageup": "Page Up",
    "pgup": "Page Up",
    "pagedown": "Page Down",
    "pgdn": "Page Down",
    "pagedn": "Page Down",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
    "capslock": "Caps Lock",
    "numlock": "Num Lock",
    "scrolllock": "Scroll Lock",
    "printscreen": "PrtSc",
    "pause": "Pause",
    "application": "Menu",
    "power": "Power",
    "play": "Play",
    "next": "Next",
    "previous": "Prev",
    "prev": "Prev",
    "stop": "Stop",
    "mute": "Mute",
    "volumeup": "Vol +",
    "volumedown": "Vol −",
    "calculator": "Calc",
    "favorites": "Favorites",
    "screenlock": "Lock",
    "screenbrightnessup": "Bright +",
    "screenbrightnessdown": "Bright −",
    "webpagehome": "Home page",
    "webpageback": "Back",
    "webpageforward": "Forward",
}

NUMPAD_WORDS = {
    "numpadenter": "Num Enter",
    "numpaddot": "Num .",
    "numpadplus": "Num +",
    "numpadminus": "Num −",
    "numpadslash": "Num /",
    "numpadasterisk": "Num *",
    "numpadequal": "Num =",
}

ACTION_LABEL = {"ccw": "Left", "press": "Press", "cw": "Right"}
ACTION_GLYPH = {"ccw": "↺", "press": "●", "cw": "↻"}
ACTION_TITLE = {"ccw": "Turn left", "press": "Press", "cw": "Turn right"}

INSERTS = (
    ("Ctrl", "ctrl"),
    ("Shift", "shift"),
    ("Alt", "alt"),
    ("Win", "win"),
    ("Enter", "enter"),
    ("Tab", "tab"),
    ("Esc", "escape"),
    ("⌫", "backspace"),
    ("Del", "delete"),
    ("Space", "space"),
    ("←", "left"),
    ("→", "right"),
    ("↑", "up"),
    ("↓", "down"),
    ("Play", "play"),
    ("Prev", "previous"),
    ("Next", "next"),
    ("Mute", "mute"),
    ("Vol −", "volumedown"),
    ("Vol +", "volumeup"),
    ("Click", "click"),
    ("Right", "rclick"),
    ("Wheel ↑", "wheelup"),
    ("Wheel ↓", "wheeldown"),
)

Target = tuple


@dataclass
class KeyGeom:
    row: int
    col: int
    box: tuple[float, float, float, float]


@dataclass
class KnobGeom:
    index: int
    center: tuple[float, float]
    radius: float
    pills: dict[str, tuple[float, float, float, float]]


@dataclass
class DeviceLayout:
    plate: tuple[float, float, float, float] | None
    knobs: list[KnobGeom]
    keys: list[KeyGeom]


@dataclass
class Hotspot:
    kind: str
    target: Target
    box: tuple[float, float, float, float]
    cx: float = 0
    cy: float = 0
    radius: float = 0


def enable_dpi() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def cell_text(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return macro_to_text(value)
    except ValueError:
        return value


def glow_color(row: int, col: int, rows: int, cols: int) -> str:
    stops = (
        (0.00, (198, 245, 80)),
        (0.38, (70, 255, 190)),
        (0.62, (80, 170, 255)),
        (0.82, (190, 100, 255)),
        (1.00, (255, 70, 120)),
    )
    t = (row + 0.35) / max(rows, 1)
    if cols > 1:
        t += (col / (cols - 1) - 0.5) * 0.08
    t = min(1.0, max(0.0, t))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            span = (t1 - t0) or 1
            u = (t - t0) / span
            rgb = tuple(int(a + (b - a) * u) for a, b in zip(c0, c1))
            return "#{:02x}{:02x}{:02x}".format(*rgb)
    red, green, blue = stops[-1][1]
    return f"#{red:02x}{green:02x}{blue:02x}"


def split_modifiers(token: str) -> tuple[list[str], str]:
    raw = token.strip()
    mods: list[str] = []
    while "-" in raw.split("(", 1)[0]:
        piece, rest = raw.split("-", 1)
        if piece.lower() not in MODIFIER_ALIASES:
            break
        mods.append(MODIFIER_ALIASES[piece.lower()])
        raw = rest
    return mods, raw


def pretty_mouse(raw: str) -> str | None:
    simple = {
        "click": "Click",
        "lclick": "Click",
        "rclick": "Right click",
        "mclick": "Middle click",
        "wheelup": "Wheel up",
        "wheeldown": "Wheel down",
    }
    click = re.fullmatch(r"click\(([^)]*)\)", raw, re.IGNORECASE)
    if click:
        buttons = click.group(1).replace("lclick", "left")
        buttons = buttons.replace("rclick", "right").replace("mclick", "middle")
        parts = [part.strip().capitalize() for part in buttons.split("+") if part.strip()]
        return "+".join(parts) + " click" if parts else "Click"
    move = re.fullmatch(r"move\(([^)]*)\)", raw, re.IGNORECASE)
    if move:
        return "Move " + move.group(1)
    drag = re.fullmatch(r"drag\(([^)]*)\)", raw, re.IGNORECASE)
    if drag:
        return "Drag " + drag.group(1)
    wheel = re.fullmatch(r"wheel\(([^)]*)\)", raw, re.IGNORECASE)
    if wheel:
        return "Wheel " + wheel.group(1)
    if re.fullmatch(
        r"(?:click|lclick|rclick|mclick)(?:\+(?:click|lclick|rclick|mclick))+",
        raw,
        re.IGNORECASE,
    ):
        names = {"click": "Left", "lclick": "Left", "rclick": "Right", "mclick": "Middle"}
        return "+".join(names[part.lower()] for part in raw.split("+")) + " click"
    return simple.get(raw.lower())


def pretty_key(raw: str) -> str:
    if not raw:
        return ""
    mouse = pretty_mouse(raw)
    if mouse:
        return mouse
    lowered = raw.lower()
    if lowered in KEY_WORDS:
        return KEY_WORDS[lowered]
    if lowered in NUMPAD_WORDS:
        return NUMPAD_WORDS[lowered]
    if re.fullmatch(r"numpad\d", lowered):
        return "Num " + lowered[-1]
    if re.fullmatch(r"f\d{1,2}", lowered):
        return lowered.upper()
    if len(raw) == 1:
        return raw.upper()
    return raw


def pretty_token(token: str) -> str:
    delay = re.fullmatch(r"delay\((\d+)\)", token.strip(), re.IGNORECASE)
    if delay:
        return f"{delay.group(1)}ms"
    mods, raw = split_modifiers(token)
    canon = MODIFIER_ALIASES.get(raw.lower())
    if canon in CANON_MOD:
        mods.append(canon)
        raw = ""
    names = [CANON_MOD.get(mod, mod.title()) for mod in mods]
    label = pretty_key(raw)
    if label:
        names.append(label)
    return "+".join(names)


def _scan_macro(text: str):
    i = 0
    while i < len(text):
        if text.startswith("{{", i):
            yield "{", False
            i += 2
            continue
        if text.startswith("}}", i):
            yield "}", False
            i += 2
            continue
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end < 0:
                yield text[i:], False
                return
            yield pretty_token(text[i + 1 : end]), True
            i = end + 1
            continue
        j = i
        while (
            j < len(text)
            and text[j] != "{"
            and not text.startswith("}}", j)
        ):
            j += 1
        yield text[i:j], False
        i = j


def pretty_macro(text: str) -> str:
    """Short label for a macros.txt action. Empty and '-' stay blank."""
    raw = (text or "").strip()
    if raw in {"", "-"}:
        return ""
    rendered = [(part, is_token) for part, is_token in _scan_macro(raw) if part != ""]
    if not rendered:
        return ""
    pieces = [rendered[0][0]]
    for index in range(1, len(rendered)):
        part, is_token = rendered[index]
        prev, prev_token = rendered[index - 1]
        glue = ""
        if (is_token or prev_token) and not prev.endswith(" ") and not part.startswith(" "):
            glue = " "
        pieces.append(glue + part)
    return "".join(pieces)


def wrap_atoms(text: str, max_width: float, measure, break_words: bool = True) -> list[str]:
    atoms = re.findall(r"\S+?\+|\S+", text) or ([text] if text else [])
    lines: list[str] = []
    current = ""
    for atom in atoms:
        trial = atom if not current else (current + atom if current.endswith("+") else current + " " + atom)
        if measure(trial) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
            current = ""
        if measure(atom) <= max_width or not break_words:
            current = atom
            continue
        buf = ""
        for ch in atom:
            if measure(buf + ch) <= max_width:
                buf += ch
            else:
                if buf:
                    lines.append(buf)
                buf = ch
        current = buf
    if current:
        lines.append(current)
    return _pull_orphan(lines)


def _pull_orphan(lines: list[str]) -> list[str]:
    """Move a trailing symbol onto the previous word: 'home ↵ cls' / '↵' -> two pairs."""
    if len(lines) < 2:
        return lines
    last = lines[-1]
    if len(last) > 2 or any(ch.isalnum() for ch in last) or " " not in lines[-2]:
        return lines
    head, _, tail = lines[-2].rpartition(" ")
    if not head:
        return lines
    updated = lines[:]
    updated[-2] = head
    updated[-1] = f"{tail} {last}"
    return updated


def clip_lines(lines: list[str], max_lines: int, measure, max_width: float) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    last = kept[-1]
    while last and measure(last + "…") > max_width:
        last = last[:-1]
    kept[-1] = (last + "…") if last else "…"
    return kept


def default_mapping() -> Mapping:
    mapping = Mapping(rows=3, columns=4, knobs=3)
    for _ in range(3):
        mapping.layers.append(empty_layer(3, 4, 3))
    return mapping


def compute_layout(
    width: float, height: float, rows: int, cols: int, nknobs: int
) -> DeviceLayout:
    rows = max(int(rows), 1)
    cols = max(int(cols), 1)
    nknobs = max(int(nknobs), 0)
    margin = 16
    caption_h = 28
    avail_w = max(80.0, width - margin * 2)
    avail_h = max(80.0, height - margin * 2 - caption_h)
    gap = 10.0
    plate_gap = 14.0

    plate_h = min(188.0, avail_h * 0.30) if nknobs else 0.0
    stack_h = min(102.0, avail_h * 0.18) if nknobs else 0.0
    overhead = (plate_h + stack_h + plate_gap) if nknobs else 0.0
    grid_room = max(36.0, avail_h - overhead)
    key = min(
        (avail_w - gap * (cols - 1)) / cols,
        (grid_room - gap * (rows - 1)) / rows,
    )
    key = min(max(key, 8.0), 116.0)
    grid_w = cols * key + gap * (cols - 1)
    grid_h = rows * key + gap * (rows - 1)

    content_w = grid_w
    if nknobs:
        content_w = min(avail_w, max(grid_w, 150.0 * nknobs))
    content_h = overhead + grid_h
    if content_h > avail_h and nknobs:
        spare = content_h - avail_h
        plate_h = max(110.0, plate_h - spare * 0.5)
        stack_h = max(68.0, stack_h - spare * 0.25)
        overhead = plate_h + stack_h + plate_gap
        grid_room = max(36.0, avail_h - overhead)
        key = min(key, (grid_room - gap * (rows - 1)) / rows)
        key = max(key, 8.0)
        grid_w = cols * key + gap * (cols - 1)
        grid_h = rows * key + gap * (rows - 1)
        content_w = min(avail_w, max(grid_w, content_w))
        content_h = overhead + grid_h

    x0 = margin + (avail_w - content_w) / 2
    y0 = margin + max(0.0, (avail_h - content_h) / 2)
    grid_x = x0 + (content_w - grid_w) / 2
    grid_y = y0 + overhead

    keys = []
    for row in range(rows):
        for col in range(cols):
            x = grid_x + col * (key + gap)
            y = grid_y + row * (key + gap)
            keys.append(KeyGeom(row, col, (x, y, x + key, y + key)))

    plate = None
    knobs: list[KnobGeom] = []
    if nknobs:
        plate = (x0, y0, x0 + content_w, y0 + plate_h)
        weights = [0.92, 0.92, 1.22] if nknobs == 3 else [1.0] * nknobs
        total = sum(weights)
        cursor = x0
        columns: list[tuple[float, float]] = []
        for weight in weights:
            span = content_w * weight / total
            columns.append((cursor, cursor + span))
            cursor += span
        pill_gap = 3.0
        pill_h = (stack_h - 4 - pill_gap * 2) / 3
        stack_top = y0 + plate_h + 2
        for index, (left, right) in enumerate(columns):
            span = right - left
            cx = (left + right) / 2
            y_frac = 0.50
            radius_frac = 0.30
            span_frac = 0.30
            if nknobs == 3 and index == 1:
                y_frac = 0.44
            if nknobs == 3 and index == nknobs - 1:
                y_frac = 0.54
                radius_frac = 0.40
                span_frac = 0.34
            cy = y0 + plate_h * y_frac
            radius = min(plate_h * radius_frac, span * span_frac)
            radius = min(radius, cy - (y0 + 8), (y0 + plate_h - 6) - cy)
            radius = max(radius, 12.0)
            pill_w = max(24.0, span - 8)
            px = cx - pill_w / 2
            pills = {}
            for action_index, action in enumerate(KNOB_ACTIONS):
                py = stack_top + action_index * (pill_h + pill_gap)
                pills[action] = (px, py, px + pill_w, py + pill_h)
            knobs.append(KnobGeom(index, (cx, cy), radius, pills))
    return DeviceLayout(plate, knobs, keys)


def _outset(box: tuple[float, float, float, float], pad: float):
    x1, y1, x2, y2 = box
    return (x1 - pad, y1 - pad, x2 + pad, y2 + pad)


def _round_rect(canvas: tk.Canvas, box, radius: float, **kwargs):
    x1, y1, x2, y2 = box
    radius = min(radius, max(0, (x2 - x1) / 2), max(0, (y2 - y1) / 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


class KeypadApp(tk.Tk):
    def __init__(
        self,
        txt_path: Path,
        yaml_path: Path,
        tool: str | None = None,
        *,
        show: bool = True,
    ) -> None:
        enable_dpi()
        super().__init__()
        self.txt_path = Path(txt_path)
        self.yaml_path = Path(yaml_path)
        self.tool = tool
        self.mapping = default_mapping()
        self.snapshot = mapping_to_text(self.mapping)
        self.layer_index = 0
        self.selection: Target | None = None
        self.hover: Target | None = None
        self._invalid = False
        self._loading = False
        self._busy = False
        self._fonts: dict[tuple[int, str], tkfont.Font] = {}
        self.hotspots: list[Hotspot] = []
        self._canvas_size = (0, 0)

        self.title("Macro Keyboard")
        self.configure(bg=BG)
        self.minsize(980, 700)
        self.withdraw()
        self._build()
        self._load_initial()
        self.update_idletasks()
        self._place_window()
        self.redraw()
        self.update_title()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if show:
            self.deiconify()

    def _place_window(self) -> None:
        width, height = 1180, 760
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _font(self, size: int, weight: str = "normal") -> tkfont.Font:
        key = (size, weight)
        font = self._fonts.get(key)
        if font is None:
            font = tkfont.Font(family=FONT, size=size, weight=weight)
            self._fonts[key] = font
        return font

    def _build(self) -> None:
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(side="top", fill="x")
        self.layer_bar = tk.Frame(toolbar, bg=BG)
        self.layer_bar.pack(side="left", padx=14, pady=12)

        actions = tk.Frame(toolbar, bg=BG)
        actions.pack(side="right", padx=14, pady=12)
        self.reload_btn = self._make_button(actions, "Reload", self.reload_from_disk)
        self.save_btn = self._make_button(actions, "Save", self.save_to_disk)
        self.upload_btn = self._make_button(
            actions, "Upload", self.upload, primary=True
        )
        self.upload_btn.pack(side="right")
        self.save_btn.pack(side="right", padx=(0, 8))
        self.reload_btn.pack(side="right", padx=(0, 8))

        status = tk.Frame(self, bg=BG)
        status.pack(side="bottom", fill="x")
        self.file_label = tk.Label(
            status, text=self.txt_path.name, bg=BG, fg=DIM, font=(FONT, 9)
        )
        self.file_label.pack(side="left", padx=14, pady=8)
        self.state_label = tk.Label(status, text="", bg=BG, fg=DIM, font=(FONT, 9))
        self.state_label.pack(side="right", padx=14, pady=8)
        tk.Frame(self, bg=LINE, height=1).pack(side="bottom", fill="x")
        tk.Frame(self, bg=LINE, height=1).pack(side="top", fill="x")

        body = tk.Frame(self, bg=BG)
        body.pack(side="top", fill="both", expand=True)
        self.canvas = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        tk.Frame(body, bg=LINE, width=1).pack(side="left", fill="y")
        self.panel = tk.Frame(body, bg=PANEL, width=392)
        self.panel.pack(side="left", fill="y")
        self.panel.pack_propagate(False)

        self.hint_frame = tk.Frame(self.panel, bg=PANEL)
        self.edit_frame = tk.Frame(self.panel, bg=PANEL)
        self._build_hint()
        self._build_editor()
        self.hint_frame.pack(fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<Configure>", self.on_configure)
        self.bind_all("<Control-s>", self._save_event)
        self.bind_all("<Control-S>", self._save_event)
        for number in range(1, 10):
            self.bind_all(f"<Control-Key-{number}>", self._layer_event(number - 1))

    def _build_hint(self) -> None:
        wrap = tk.Frame(self.hint_frame, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=22, pady=22)
        tk.Label(
            wrap,
            text="Select a key or knob",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            wrap,
            text=(
                "The picture is macros.txt.\n"
                "[1,1] is the upper-left key.\n"
                "Knob 1 is the left knob. Each knob has\n"
                "turn left, press, and turn right.\n\n"
                "Type letters as themselves. Put keys and\n"
                "combos in braces, such as {ctrl-c} or\n"
                "{win-r}notepad{enter}. Use - to clear.\n\n"
                "Ctrl+S saves. Upload writes the keypad."
            ),
            bg=PANEL,
            fg=DIM,
            font=(FONT, 10),
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(12, 0))

    def _build_editor(self) -> None:
        wrap = tk.Frame(self.edit_frame, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=18, pady=16)
        self.title_label = tk.Label(
            wrap, text="", bg=PANEL, fg=TEXT, font=(FONT, 16, "bold"), anchor="w"
        )
        self.title_label.pack(fill="x")
        self.sub_label = tk.Label(
            wrap, text="", bg=PANEL, fg=DIM, font=(FONT, 9), anchor="w"
        )
        self.sub_label.pack(fill="x", pady=(2, 8))
        self.headline = tk.Label(
            wrap,
            text="",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 13),
            anchor="w",
            justify="left",
            wraplength=340,
        )
        self.headline.pack(fill="x", pady=(0, 10))
        tk.Label(
            wrap,
            text="Text in macros.txt",
            bg=PANEL,
            fg=FAINT,
            font=(FONT, 8),
            anchor="w",
        ).pack(fill="x")
        self.editor = tk.Text(
            wrap,
            height=3,
            bg="#101318",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=(MONO, 12),
            wrap="word",
            undo=True,
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=ACCENT,
        )
        self.editor.pack(fill="x", pady=(4, 4))
        self.error_label = tk.Label(
            wrap,
            text="",
            bg=PANEL,
            fg=DANGER,
            font=(FONT, 9),
            anchor="w",
            justify="left",
            wraplength=340,
        )
        self.error_label.pack(fill="x")
        tk.Label(
            wrap, text="Insert", bg=PANEL, fg=FAINT, font=(FONT, 8), anchor="w"
        ).pack(fill="x", pady=(8, 4))

        chips = tk.Frame(wrap, bg=PANEL)
        chips.pack(fill="x")
        for index, (label, token) in enumerate(INSERTS):
            btn = self._make_button(
                chips, label, lambda token=token: self.insert_token(token), compact=True
            )
            btn.grid(row=index // 4, column=index % 4, padx=3, pady=3, sticky="ew")
        for column in range(4):
            chips.columnconfigure(column, weight=1)

        self.clear_btn = self._make_button(wrap, "Clear", self.clear_binding)
        self.clear_btn.pack(anchor="w", pady=(12, 8))
        tk.Label(
            wrap,
            text="Esc undoes a broken edit. {{ and }} type real braces.",
            bg=PANEL,
            fg=FAINT,
            font=(FONT, 8),
            anchor="w",
            justify="left",
            wraplength=340,
        ).pack(fill="x")
        self.editor.bind("<<Modified>>", self.on_modified)
        self.editor.bind("<Escape>", self._revert_event)
        self.editor.bind("<Return>", lambda _e: "break")
        self.editor.bind("<KP_Enter>", lambda _e: "break")

    def _make_button(self, parent, text, command, primary=False, compact=False, selected=False):
        if primary:
            bg, fg, active = ACCENT, ACCENT_INK, "#b6f3ff"
        elif selected:
            bg, fg, active = ACCENT_BG, ACCENT, "#1c5160"
        else:
            bg, fg, active = RAISED, TEXT, "#2c3340"
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg if not primary else ACCENT_INK,
            disabledforeground=FAINT,
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=8 if compact else 12,
            pady=3 if compact else 6,
            font=(FONT, 9 if compact else 10),
            cursor="hand2",
        )

    def _load_initial(self) -> None:
        if self.txt_path.exists():
            try:
                self.mapping = text_to_mapping(
                    self.txt_path.read_text(encoding="utf-8")
                )
                self.snapshot = mapping_to_text(self.mapping)
                self._note(f"Loaded {self.txt_path.name}")
            except (OSError, ValueError, yaml.YAMLError) as exc:
                messagebox.showerror("Could not load macros.txt", str(exc))
                self._load_yaml_or_default()
        else:
            self._load_yaml_or_default()
        self.layer_index = 0 if self.mapping.layers else 0
        if not self.mapping.layers:
            self.mapping.layers.append(
                empty_layer(self.mapping.rows, self.mapping.columns, self.mapping.knobs)
            )
        self.refresh_layer_buttons()

    def _load_yaml_or_default(self) -> None:
        if self.yaml_path.exists():
            try:
                self.mapping = load_yaml_mapping(self.yaml_path)
                self.snapshot = mapping_to_text(self.mapping)
                self._note(f"Loaded {self.yaml_path.name}")
                return
            except (OSError, ValueError, yaml.YAMLError) as exc:
                messagebox.showerror("Could not load macros.yaml", str(exc))
        self.mapping = default_mapping()
        self.snapshot = mapping_to_text(self.mapping)
        self._note("New mapping")

    def refresh_layer_buttons(self) -> None:
        for child in self.layer_bar.winfo_children():
            child.destroy()
        for index in range(len(self.mapping.layers)):
            button = self._make_button(
                self.layer_bar,
                f"Layer {index + 1}",
                lambda i=index: self.set_layer(i),
                selected=index == self.layer_index,
            )
            button.pack(side="left", padx=(0, 6))
        add = self._make_button(self.layer_bar, "+", self.add_layer)
        add.pack(side="left", padx=(2, 0))
        if len(self.mapping.layers) > 1:
            remove = self._make_button(self.layer_bar, "−", self.remove_layer)
            remove.pack(side="left", padx=(6, 0))

    def current_layer(self):
        return self.mapping.layers[self.layer_index]

    def get_binding(self, target: Target) -> str | None:
        layer = self.current_layer()
        if target[0] == "button":
            return layer.buttons[target[1]][target[2]]
        return getattr(layer.knobs[target[1]], target[2])

    def set_binding(self, target: Target, value: str | None) -> None:
        layer = self.current_layer()
        if target[0] == "button":
            layer.buttons[target[1]][target[2]] = value
            return
        setattr(layer.knobs[target[1]], target[2], value)

    def selection_title(self) -> str:
        if not self.selection:
            return ""
        kind = self.selection[0]
        if kind == "button":
            return f"Key {self.selection[1] + 1},{self.selection[2] + 1}"
        return f"Knob {self.selection[1] + 1} · {ACTION_TITLE[self.selection[2]]}"

    def selection_subtitle(self) -> str:
        if not self.selection:
            return ""
        layer = self.layer_index + 1
        if self.selection[0] == "button":
            return f"Layer {layer}  ·  [{self.selection[1] + 1},{self.selection[2] + 1}]"
        return f"Layer {layer}  ·  knob {self.selection[1] + 1} {self.selection[2]}"

    def show_hint(self) -> None:
        self.edit_frame.pack_forget()
        if not self.hint_frame.winfo_ismapped():
            self.hint_frame.pack(fill="both", expand=True)

    def show_edit(self) -> None:
        self.hint_frame.pack_forget()
        if not self.edit_frame.winfo_ismapped():
            self.edit_frame.pack(fill="both", expand=True)

    def set_editor_text(self, text: str) -> None:
        self._loading = True
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_modified(False)
        self._loading = False

    def load_editor(self) -> None:
        if self.selection is None:
            self.show_hint()
            return
        self.show_edit()
        text = cell_text(self.get_binding(self.selection))
        self.set_editor_text(text)
        self.title_label.configure(text=self.selection_title())
        self.sub_label.configure(text=self.selection_subtitle())
        pretty = pretty_macro(text)
        self.headline.configure(text=pretty or "Empty", fg=TEXT if pretty else DIM)
        self.error_label.configure(text="")
        self._invalid = False
        if text == "-":
            self.editor.tag_add("sel", "1.0", "end-1c")
        self.editor.mark_set("insert", "end-1c")
        self.editor.focus_set()

    def apply_editor(self) -> bool:
        if self.selection is None:
            return True
        text = self.editor.get("1.0", "end-1c").strip()
        try:
            value = text_to_macro(text)
        except ValueError as exc:
            self._invalid = True
            self.error_label.configure(text=str(exc))
            self.headline.configure(text="Can't parse this yet", fg=DANGER)
            self.update_title()
            self.redraw()
            return False
        self._invalid = False
        self.error_label.configure(text="")
        self.set_binding(self.selection, value)
        pretty = pretty_macro(text)
        self.headline.configure(text=pretty or "Empty", fg=TEXT if pretty else DIM)
        self.update_title()
        self.redraw()
        return True

    def on_modified(self, _event=None) -> None:
        if self._loading:
            self.editor.edit_modified(False)
            return
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
            self.apply_editor()

    def insert_token(self, token: str) -> None:
        if self.selection is None:
            return
        snippet = "{" + token + "}"
        current = self.editor.get("1.0", "end-1c").strip()
        if current in {"", "-"}:
            self.set_editor_text(snippet)
        else:
            try:
                self.editor.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            self.editor.insert("insert", snippet)
            self.editor.edit_modified(False)
        self.apply_editor()
        self.editor.focus_set()

    def clear_binding(self) -> None:
        if self.selection is None:
            return
        self.set_editor_text("-")
        self.apply_editor()

    def _blocked(self) -> bool:
        if self._invalid:
            self._note("Fix this macro first, or press Esc to undo it.")
            return True
        return False

    def select(self, target: Target | None) -> None:
        if target == self.selection:
            if target is not None:
                self.editor.focus_set()
            return
        if target is not None and self._blocked():
            return
        self.selection = target
        self.load_editor()
        self.redraw()

    def set_layer(self, index: int) -> None:
        if not (0 <= index < len(self.mapping.layers)) or index == self.layer_index:
            return
        if self._blocked():
            return
        self.layer_index = index
        self.refresh_layer_buttons()
        self.load_editor()
        self.redraw()

    def add_layer(self) -> None:
        if self._blocked():
            return
        self.mapping.layers.append(
            empty_layer(self.mapping.rows, self.mapping.columns, self.mapping.knobs)
        )
        self.layer_index = len(self.mapping.layers) - 1
        self.refresh_layer_buttons()
        self.load_editor()
        self.redraw()
        self.update_title()

    def remove_layer(self) -> None:
        if len(self.mapping.layers) <= 1 or self._blocked():
            return
        number = self.layer_index + 1
        if not messagebox.askyesno(
            "Remove layer",
            f"Remove layer {number}? This stays on screen until you save.",
        ):
            return
        del self.mapping.layers[self.layer_index]
        self.layer_index = min(self.layer_index, len(self.mapping.layers) - 1)
        self.selection = None
        self.refresh_layer_buttons()
        self.show_hint()
        self.redraw()
        self.update_title()

    def is_dirty(self) -> bool:
        if self._invalid:
            return True
        return mapping_to_text(self.mapping) != self.snapshot

    def update_title(self) -> None:
        dirty = self.is_dirty()
        self.title("Macro Keyboard" + (" — unsaved" if dirty else ""))
        if self._busy:
            return
        self.state_label.configure(
            text="Unsaved changes" if dirty else "No changes",
            fg=WARN if dirty else DIM,
        )

    def _note(self, text: str, color: str = DIM) -> None:
        self.state_label.configure(text=text, fg=color)

    def save_to_disk(self) -> bool:
        if self.selection is not None and not self.apply_editor():
            self._note("Fix this macro before saving.", DANGER)
            return False
        text = mapping_to_text(self.mapping)
        try:
            self.txt_path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        self.snapshot = text
        self.update_title()
        self._note(f"Saved {self.txt_path.name}", OK)
        return True

    def reload_from_disk(self) -> None:
        if self._busy:
            return
        if self.is_dirty() and not messagebox.askyesno(
            "Reload", "Discard unsaved changes and reload the file?"
        ):
            return
        self._invalid = False
        self.selection = None
        self._load_initial()
        self.layer_index = min(self.layer_index, max(0, len(self.mapping.layers) - 1))
        self.refresh_layer_buttons()
        self.show_hint()
        self.redraw()
        self.update_title()

    def upload(self) -> None:
        if self._busy:
            return
        if self.selection is not None and not self.apply_editor():
            self._note("Fix this macro before uploading.", DANGER)
            return
        if not messagebox.askyesno(
            "Upload to keypad",
            "Save macros.txt and upload it to the keypad?\n\n"
            "Plug the keypad in with a USB cable.",
        ):
            return
        if not self.save_to_disk():
            return
        self._busy = True
        self._set_actions_enabled(False)
        self._note("Uploading…", ACCENT)
        self.configure(cursor="watch")

        def work() -> None:
            error = None
            try:
                cmd_to_yaml(self.txt_path, self.yaml_path)
                exe = find_keyboard_tool(self.tool)
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                for action in ("validate", "upload"):
                    proc = subprocess.run(
                        [str(exe), action, str(self.yaml_path)],
                        capture_output=True,
                        text=True,
                        check=False,
                        creationflags=flags,
                    )
                    if proc.returncode != 0:
                        detail = (proc.stderr or proc.stdout or f"{action} failed").strip()
                        raise RuntimeError(detail)
            except Exception as exc:
                error = str(exc)
            self.after(0, lambda: self._finish_upload(error))

        threading.Thread(target=work, daemon=True).start()

    def _finish_upload(self, error: str | None) -> None:
        if not self.winfo_exists():
            return
        self._busy = False
        self.configure(cursor="")
        self._set_actions_enabled(True)
        self.update_title()
        if error:
            self._note("Upload failed", DANGER)
            messagebox.showerror("Upload failed", error)
        else:
            self._note("Uploaded to the keypad", OK)

    def _set_actions_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.reload_btn, self.save_btn, self.upload_btn):
            button.configure(state=state)

    def on_close(self) -> None:
        if self.is_dirty():
            answer = messagebox.askyesnocancel(
                "Unsaved changes", "Save changes to macros.txt before closing?"
            )
            if answer is None:
                return
            if answer and not self.save_to_disk():
                return
        self.destroy()

    def _save_event(self, _event=None):
        self.save_to_disk()
        return "break"

    def _layer_event(self, index: int):
        def handler(_event=None):
            self.set_layer(index)
            return "break"

        return handler

    def _revert_event(self, _event=None):
        if self._invalid:
            self._invalid = False
            self.load_editor()
            self.redraw()
            self.update_title()
        else:
            self.selection = None
            self.show_hint()
            self.redraw()
        return "break"

    def on_configure(self, event) -> None:
        if event.widget is not self.canvas:
            return
        size = (event.width, event.height)
        if size == self._canvas_size or event.width < 20 or event.height < 20:
            return
        self._canvas_size = size
        self.redraw()

    def on_click(self, event) -> None:
        target = self.hit(event.x, event.y)
        if target is not None:
            self.select(target)

    def on_motion(self, event) -> None:
        target = self.hit(event.x, event.y)
        if target != self.hover:
            self.hover = target
            self.canvas.configure(cursor="hand2" if target else "")
            self.redraw()

    def on_leave(self, _event) -> None:
        if self.hover is not None:
            self.hover = None
            self.canvas.configure(cursor="")
            self.redraw()

    def hit(self, x: float, y: float) -> Target | None:
        for spot in reversed(self.hotspots):
            if spot.kind == "circle":
                dx = x - spot.cx
                dy = y - spot.cy
                if dx * dx + dy * dy <= spot.radius * spot.radius:
                    return spot.target
                continue
            x1, y1, x2, y2 = spot.box
            if x1 <= x <= x2 and y1 <= y <= y2:
                return spot.target
        return None

    def redraw(self) -> None:
        width = max(self.canvas.winfo_width(), 80)
        height = max(self.canvas.winfo_height(), 80)
        layout = compute_layout(
            width,
            height,
            self.mapping.rows,
            self.mapping.columns,
            self.mapping.knobs,
        )
        self.canvas.delete("all")
        self.hotspots = []
        self._draw_device(layout)
        caption = (
            f"{self.mapping.model}  ·  {self.mapping.rows}×{self.mapping.columns}"
            f"  ·  {self.mapping.knobs} knobs  ·  {self.mapping.orientation}"
        )
        self.canvas.create_text(
            width / 2,
            height - 16,
            text=caption,
            fill=FAINT,
            font=(FONT, 9),
        )

    def _draw_device(self, layout: DeviceLayout) -> None:
        boxes = [key.box for key in layout.keys]
        if layout.plate:
            boxes.append(layout.plate)
        for knob in layout.knobs:
            boxes.extend(knob.pills.values())
        if not boxes:
            return
        chassis = (
            min(box[0] for box in boxes) - 18,
            min(box[1] for box in boxes) - 16,
            max(box[2] for box in boxes) + 18,
            max(box[3] for box in boxes) + 18,
        )
        _round_rect(self.canvas, chassis, 26, fill=CHASSIS, outline="#232830")
        if layout.plate:
            _round_rect(self.canvas, layout.plate, 20, fill=SILVER, outline=SILVER_EDGE)
            px1, py1, px2, _py2 = layout.plate
            for offset, color in enumerate(("#d5dde4", "#c3ccd3", "#b4bdc5", "#aeb6be")):
                y = py1 + 16 + offset * 3
                self.canvas.create_line(px1 + 24, y, px2 - 24, y, fill=color)

        layer = self.current_layer()
        rows = self.mapping.rows
        cols = self.mapping.columns
        for key in layout.keys:
            value = None
            if key.row < len(layer.buttons) and key.col < len(layer.buttons[key.row]):
                value = layer.buttons[key.row][key.col]
            self._draw_key(key, value, rows, cols)

        for knob in layout.knobs:
            self._draw_knob(knob, layer.knobs[knob.index] if knob.index < len(layer.knobs) else Knob())

    def _draw_key(self, key: KeyGeom, value: str | None, rows: int, cols: int) -> None:
        target = ("button", key.row, key.col)
        selected = target == self.selection
        hovered = target == self.hover
        color = glow_color(key.row, key.col, rows, cols)
        if selected:
            _round_rect(self.canvas, _outset(key.box, 7), 18, fill=ACCENT, outline="")
        _round_rect(self.canvas, _outset(key.box, 3), 16, fill=color, outline="")
        _round_rect(self.canvas, key.box, 14, fill=KEYCAP, outline="#101218")
        if selected:
            _round_rect(self.canvas, key.box, 14, fill="", outline=ACCENT, width=3)
        elif hovered:
            _round_rect(self.canvas, key.box, 14, fill="", outline="#3d4654", width=2)
        x1, y1, x2, y2 = key.box
        size = x2 - x1
        if size >= 68:
            self.canvas.create_text(
                x1 + 10,
                y1 + 8,
                text=f"{key.row + 1},{key.col + 1}",
                anchor="nw",
                fill=FAINT,
                font=(FONT, 8),
            )
        label = pretty_macro(cell_text(value))
        inset_top = 22 if size >= 68 else 8
        lines, font_size = self._fit_lines(label, size - 18, size - inset_top - 10)
        if lines:
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 + (6 if size >= 68 else 0),
                text="\n".join(lines),
                fill=TEXT if not self._invalid or not selected else DANGER,
                font=(FONT, font_size),
                justify="center",
            )
        self.hotspots.append(Hotspot("rect", target, key.box))

    def _draw_knob(self, geom: KnobGeom, knob: Knob) -> None:
        cx, cy = geom.center
        radius = geom.radius
        selected_knob = (
            self.selection is not None
            and self.selection[0] == "knob"
            and self.selection[1] == geom.index
        )
        self.canvas.create_oval(
            cx - radius - 2,
            cy - radius + 3,
            cx + radius + 2,
            cy + radius + 6,
            fill="#070809",
            outline="",
        )
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, fill=SILVER, outline=""
        )
        ticks = 22 if radius < 42 else 30
        for step in range(ticks):
            angle = math.tau * step / ticks
            outer = radius * 0.94
            inner = radius * 0.76
            self.canvas.create_line(
                cx + inner * math.cos(angle),
                cy + inner * math.sin(angle),
                cx + outer * math.cos(angle),
                cy + outer * math.sin(angle),
                fill="#2c3238",
                width=2,
            )
        face = radius * 0.70
        self.canvas.create_oval(
            cx - face, cy - face, cx + face, cy + face, fill=KNOB_FACE, outline=""
        )
        spec = radius * 0.22
        self.canvas.create_oval(
            cx - spec,
            cy - radius * 0.34,
            cx + spec,
            cy - radius * 0.34 + spec,
            fill="#2a3038",
            outline="",
        )
        self.canvas.create_text(
            cx,
            cy + radius * 0.06,
            text=str(geom.index + 1),
            fill="#9aa4ae",
            font=(FONT, max(9, int(radius * 0.34)), "bold"),
        )
        if selected_knob:
            self.canvas.create_oval(
                cx - radius - 3,
                cy - radius - 3,
                cx + radius + 3,
                cy + radius + 3,
                outline=ACCENT,
                width=2,
            )
        self.hotspots.append(
            Hotspot(
                "circle",
                ("knob", geom.index, "press"),
                (cx - radius, cy - radius, cx + radius, cy + radius),
                cx,
                cy,
                radius,
            )
        )
        for action in KNOB_ACTIONS:
            self._draw_pill(geom, action, getattr(knob, action))

    def _draw_pill(self, geom: KnobGeom, action: str, value: str | None) -> None:
        box = geom.pills[action]
        target = ("knob", geom.index, action)
        selected = target == self.selection
        hovered = target == self.hover
        fill = ACCENT_BG if selected else ("#2a3140" if hovered else "#1e232c")
        outline = ACCENT if selected else ("#3c4554" if hovered else "#2a303a")
        _round_rect(self.canvas, box, 8, fill=fill, outline=outline, width=1)
        x1, y1, x2, y2 = box
        pretty = pretty_macro(cell_text(value)) or "—"
        glyph = ACTION_GLYPH[action]
        word = ACTION_LABEL[action]
        font_size = 9 if (y2 - y1) >= 22 else 8
        inner = max(20, (x2 - x1) - 16)
        font = self._font(font_size)
        with_word = f"{glyph}  {word}"
        if pretty != "—" and font.measure(f"{with_word}  {pretty}") > inner:
            font_size = 8
            font = self._font(8)
        if pretty == "—" or font.measure(f"{with_word}  {pretty}") <= inner:
            left = with_word
        else:
            left = glyph
        left_w = font.measure(left)
        shown = self._truncate(pretty, font, max(12, inner - left_w - 8))
        cy = (y1 + y2) / 2
        self.canvas.create_text(
            x1 + 8,
            cy,
            text=left,
            anchor="w",
            fill=ACCENT if selected else DIM,
            font=(FONT, font_size),
        )
        self.canvas.create_text(
            x2 - 8,
            cy,
            text=shown,
            anchor="e",
            fill=FAINT if shown == "—" else TEXT,
            font=(FONT, font_size),
        )
        self.hotspots.append(Hotspot("rect", target, box))

    def _truncate(self, text: str, font: tkfont.Font, max_width: float) -> str:
        if font.measure(text) <= max_width:
            return text
        trimmed = text
        while trimmed and font.measure(trimmed + "…") > max_width:
            trimmed = trimmed[:-1]
        return (trimmed + "…") if trimmed else "…"

    def _fit_lines(self, text: str, max_width: float, max_height: float):
        if not text:
            return [], 12
        for size in range(15, 7, -1):
            font = self._font(size)
            lines = wrap_atoms(text, max_width, font.measure, break_words=False)
            too_wide = any(font.measure(line) > max_width + 1 for line in lines)
            too_tall = (
                len(lines) > 3 or len(lines) * font.metrics("linespace") > max_height
            )
            if lines and not too_wide and not too_tall:
                return lines, size
        font = self._font(8)
        lines = clip_lines(
            wrap_atoms(text, max_width, font.measure), 4, font.measure, max_width
        )
        return lines, 8


def run_gui(txt_path: Path, yaml_path: Path, tool: str | None = None) -> int:
    app = KeypadApp(txt_path, yaml_path, tool)
    app.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visual editor for the macro keypad")
    parser.add_argument("--txt", type=Path, default=DEFAULT_TXT)
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML)
    parser.add_argument("--tool", default=None, help="Path to ch57x-keyboard-tool")
    args = parser.parse_args(argv)
    return run_gui(args.txt, args.yaml, args.tool)


if __name__ == "__main__":
    sys.exit(main())
