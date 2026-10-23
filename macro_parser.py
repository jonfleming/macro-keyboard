"""Convert CH57x YAML mappings to an editable text format and back.

Typeable characters stay as plain text. Keys, combos, media, and mouse
actions are wrapped in braces:

    Raspberry Pi          types that text
    {ctrl-c}              Ctrl+C
    {alt-tab}             Alt+Tab
    {win-r}cmd{enter}     Win+R, type cmd, Enter
    {f12} {escape} {delete} {shift}
    {play} {volumedown} {click}
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

MODIFIER_ORDER = (
    "ctrl",
    "shift",
    "alt",
    "win",
    "rctrl",
    "rshift",
    "ralt",
    "rwin",
)

MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "rctrl": "rctrl",
    "shift": "shift",
    "rshift": "rshift",
    "alt": "alt",
    "opt": "alt",
    "ralt": "ralt",
    "ropt": "ralt",
    "win": "win",
    "cmd": "win",
    "super": "win",
    "meta": "win",
    "rwin": "rwin",
    "rcmd": "rwin",
}

KEY_ALIASES = {
    "esc": "escape",
    "del": "delete",
    "return": "enter",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "pagedn": "pagedown",
    "prev": "previous",
    "lclick": "click",
}

MEDIA_KEYS = {
    "screenbrightnessup",
    "screenbrightnessdown",
    "next",
    "previous",
    "prev",
    "stop",
    "play",
    "mute",
    "volumeup",
    "volumedown",
    "favorites",
    "calculator",
    "screenlock",
    "webpagehome",
    "webpageback",
    "webpageforward",
}

MOUSE_RE = re.compile(
    r"^(?:(?:ctrl|shift|alt)-)?"
    r"(?:"
    r"(?:click|lclick|rclick|mclick)(?:\+(?:click|lclick|rclick|mclick))*"
    r"|click\([^)]*\)"
    r"|wheel(?:up|down|\([^)]*\))"
    r"|move\([^)]*\)"
    r"|drag\([^)]*\)"
    r")$",
    re.IGNORECASE,
)

DELAY_RE = re.compile(r"^\{delay\((\d+)\)\}", re.IGNORECASE)
LAYER_RE = re.compile(r"^===\s*Layer\s+(\d+)\s*===\s*$", re.IGNORECASE)
BUTTON_RE = re.compile(r"^\[(\d+),(\d+)\]\s?(.*)$")
KNOB_LINE_RE = re.compile(r"^knob\s+(\d+)\s*:\s*(.*)$", re.IGNORECASE)
KNOB_ACTION_RE = re.compile(
    r"^knob\s+(\d+)\s+(ccw|press|cw)\s*:\s*(.*)$", re.IGNORECASE
)
LEGACY_LINE_RE = re.compile(r"^Layer\s+(\d+),\s*(?:(\d+)\.\s*)?(.*)$", re.IGNORECASE)
CUSTOM_CODE_RE = re.compile(r"^<(\d+)>$")

# Printable key name -> (unshifted char, shifted char)
KEY_MAP: dict[str, tuple[str, str]] = {}
for letter in string.ascii_lowercase:
    KEY_MAP[letter] = (letter, letter.upper())
KEY_MAP.update(
    {
        "0": ("0", ")"),
        "1": ("1", "!"),
        "2": ("2", "@"),
        "3": ("3", "#"),
        "4": ("4", "$"),
        "5": ("5", "%"),
        "6": ("6", "^"),
        "7": ("7", "&"),
        "8": ("8", "*"),
        "9": ("9", "("),
        "space": (" ", " "),
        "dot": (".", ">"),
        "comma": (",", "<"),
        "slash": ("/", "?"),
        "semicolon": (";", ":"),
        "quote": ("'", '"'),
        "grave": ("`", "~"),
        "minus": ("-", "_"),
        "equal": ("=", "+"),
        "leftbracket": ("[", "{"),
        "rightbracket": ("]", "}"),
        "backslash": ("\\", "|"),
        "enter": ("\n", "\n"),
        "tab": ("\t", "\t"),
        "backspace": ("\b", "\b"),
    }
)

CHAR_TO_ACCORD: dict[str, str] = {}
for _name, (_unshifted, _shifted) in KEY_MAP.items():
    CHAR_TO_ACCORD[_unshifted] = _name
    if _shifted != _unshifted:
        CHAR_TO_ACCORD[_shifted] = f"shift-{_name}"

SPECIAL_TEXT = {
    "enter": "{enter}",
    "tab": "{tab}",
    "backspace": "{backspace}",
}

KNOB_ACTIONS = ("ccw", "press", "cw")
DEFAULT_MODEL = "ch57x-1"
DEFAULT_ORIENTATION = "normal"


@dataclass
class Accord:
    modifiers: list[str] = field(default_factory=list)
    code: str | None = None

    def to_yaml(self) -> str:
        parts = [m for m in MODIFIER_ORDER if m in self.modifiers]
        extra = [m for m in self.modifiers if m not in MODIFIER_ORDER]
        parts.extend(extra)
        if self.code:
            parts.append(self.code)
        return "-".join(parts)

    def as_text(self) -> str:
        if self.code in KEY_MAP and set(self.modifiers) <= {"shift"}:
            if self.code in SPECIAL_TEXT:
                return SPECIAL_TEXT[self.code]
            return KEY_MAP[self.code][1 if "shift" in self.modifiers else 0]
        if self.code == "space" and not self.modifiers:
            return " "
        rendered = self.to_yaml()
        return f"{{{rendered}}}" if rendered else ""


@dataclass
class KeyboardMacro:
    delay_ms: int | None = None
    accords: list[Accord] = field(default_factory=list)

    def to_yaml(self) -> str:
        body = ",".join(a.to_yaml() for a in self.accords)
        if self.delay_ms is not None:
            return f"{{delay({self.delay_ms})}}{body}"
        return body

    def to_text(self) -> str:
        prefix = f"{{delay({self.delay_ms})}}" if self.delay_ms is not None else ""
        body = "".join(a.as_text() for a in self.accords)
        if body == " ":
            body = "{space}"
        return prefix + body


@dataclass
class NamedMacro:
    """Media or mouse action stored as a canonical yaml token."""

    name: str
    delay_ms: int | None = None

    def to_yaml(self) -> str:
        if self.delay_ms is not None:
            return f"{{delay({self.delay_ms})}}{self.name}"
        return self.name

    def to_text(self) -> str:
        prefix = f"{{delay({self.delay_ms})}}" if self.delay_ms is not None else ""
        return f"{prefix}{{{self.name}}}"


Macro = KeyboardMacro | NamedMacro


@dataclass
class Knob:
    ccw: str | None = None
    press: str | None = None
    cw: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"ccw": self.ccw, "press": self.press, "cw": self.cw}


@dataclass
class Layer:
    buttons: list[list[str | None]]
    knobs: list[Knob]


@dataclass
class Mapping:
    model: str = DEFAULT_MODEL
    orientation: str = DEFAULT_ORIENTATION
    rows: int = 3
    columns: int = 4
    knobs: int = 3
    layers: list[Layer] = field(default_factory=list)


def canonicalize_key(name: str) -> str:
    lowered = name.strip().lower()
    if CUSTOM_CODE_RE.match(lowered):
        return lowered
    return KEY_ALIASES.get(lowered, lowered)


def canonicalize_modifier(name: str) -> str:
    lowered = name.strip().lower()
    if lowered not in MODIFIER_ALIASES:
        raise ValueError(f"Unknown modifier: {name}")
    return MODIFIER_ALIASES[lowered]


def split_delay(macro_str: str) -> tuple[int | None, str]:
    match = DELAY_RE.match(macro_str)
    if not match:
        return None, macro_str
    return int(match.group(1)), macro_str[match.end() :]


def is_mouse(token: str) -> bool:
    return bool(MOUSE_RE.match(token.strip()))


def is_media(token: str) -> bool:
    return token.strip().lower() in MEDIA_KEYS


def parse_accord(token: str) -> Accord:
    raw = token.strip()
    if not raw:
        raise ValueError("Empty key combination")

    if CUSTOM_CODE_RE.match(raw):
        return Accord(code=raw)

    # Keep "<123>" together while splitting modifiers: shift-<100>
    pieces: list[str] = []
    buf = ""
    i = 0
    while i < len(raw):
        if raw[i] == "<":
            end = raw.find(">", i)
            if end == -1:
                raise ValueError(f"Unclosed custom key code: {raw}")
            if buf:
                pieces.extend(p for p in buf.split("-") if p)
                buf = ""
            pieces.append(raw[i : end + 1])
            i = end + 1
            if i < len(raw) and raw[i] == "-":
                i += 1
            continue
        buf += raw[i]
        i += 1
    if buf:
        pieces.extend(p for p in buf.split("-") if p)

    if not pieces:
        raise ValueError(f"Empty key combination: {raw}")

    modifiers: list[str] = []
    code: str | None = None
    for index, piece in enumerate(pieces):
        lowered = piece.lower()
        is_last = index == len(pieces) - 1
        if lowered in MODIFIER_ALIASES and not (is_last and len(pieces) == 1):
            modifiers.append(canonicalize_modifier(piece))
            continue
        if is_last and lowered in MODIFIER_ALIASES and code is None:
            modifiers.append(canonicalize_modifier(piece))
            continue
        if code is not None:
            raise ValueError(f"Too many keys in combination: {raw}")
        code = canonicalize_key(piece)

    # Lone modifier (shift, ctrl-alt, …)
    if code is None and modifiers:
        return Accord(modifiers=_unique(modifiers), code=None)
    if code is None:
        raise ValueError(f"Could not parse key combination: {raw}")
    return Accord(modifiers=_unique(modifiers), code=code)


def _unique(items: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def parse_macro(macro_str: str | None) -> Macro | None:
    if macro_str is None:
        return None
    if not isinstance(macro_str, str):
        macro_str = str(macro_str)
    stripped = macro_str.strip()
    if not stripped or stripped == "-":
        return None

    delay, rest = split_delay(stripped)
    rest = rest.strip()
    if not rest:
        raise ValueError(f"Macro has delay but no keys: {macro_str}")

    if is_mouse(rest) or is_media(rest):
        name = rest.lower()
        if name == "prev":
            name = "previous"
        return NamedMacro(name=name, delay_ms=delay)

    accords = [parse_accord(part) for part in rest.split(",") if part.strip()]
    return KeyboardMacro(delay_ms=delay, accords=accords)


def macro_to_text(macro_str: str | None) -> str:
    parsed = parse_macro(macro_str)
    if parsed is None:
        return "-"
    return parsed.to_text()


def text_to_macro(text: str) -> str | None:
    parsed = parse_text_macro(text)
    if parsed is None:
        return None
    return parsed.to_yaml()


def parse_text_macro(text: str) -> Macro | None:
    if text is None:
        return None
    raw = text.strip()
    if not raw or raw == "-":
        return None

    delay: int | None = None
    accords: list[Accord] = []
    named: str | None = None
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "{" and i + 1 < len(raw) and raw[i + 1] == "{":
            accords.append(parse_accord(CHAR_TO_ACCORD["{"]))
            i += 2
            continue
        if ch == "}" and i + 1 < len(raw) and raw[i + 1] == "}":
            accords.append(parse_accord(CHAR_TO_ACCORD["}"]))
            i += 2
            continue
        if ch == "{":
            end = raw.find("}", i + 1)
            if end == -1:
                raise ValueError(f"Unclosed {{token}} in: {text}")
            token = raw[i + 1 : end].strip()
            i = end + 1
            delay_match = re.fullmatch(r"delay\((\d+)\)", token, re.IGNORECASE)
            if delay_match:
                delay = int(delay_match.group(1))
                continue
            if is_mouse(token) or is_media(token):
                name = token.lower()
                if name == "prev":
                    name = "previous"
                if named or accords:
                    raise ValueError(
                        f"Media/mouse action {{{token}}} cannot be mixed with other keys"
                    )
                named = name
                continue
            accords.append(parse_accord(token))
            continue
        if ch == "\\" and i + 1 < len(raw) and raw[i + 1] in "ntb":
            esc = {"n": "\n", "t": "\t", "b": "\b"}[raw[i + 1]]
            accords.append(parse_accord(CHAR_TO_ACCORD[esc]))
            i += 2
            continue
        if ch in CHAR_TO_ACCORD:
            accords.append(parse_accord(CHAR_TO_ACCORD[ch]))
            i += 1
            continue
        raise ValueError(f"Unsupported character {ch!r} in: {text}")

    if named is not None:
        return NamedMacro(name=named, delay_ms=delay)
    if not accords:
        return None
    return KeyboardMacro(delay_ms=delay, accords=accords)


def empty_layer(rows: int, columns: int, knob_count: int) -> Layer:
    return Layer(
        buttons=[[None] * columns for _ in range(rows)],
        knobs=[Knob() for _ in range(knob_count)],
    )


def load_yaml_mapping(path: Path | str) -> Mapping:
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return mapping_from_dict(data)


def mapping_from_dict(data: dict[str, Any]) -> Mapping:
    rows = int(data.get("rows") or 3)
    columns = int(data.get("columns") or 4)
    knob_count = int(data.get("knobs") or 0)
    mapping = Mapping(
        model=str(data.get("model") or DEFAULT_MODEL),
        orientation=str(data.get("orientation") or DEFAULT_ORIENTATION),
        rows=rows,
        columns=columns,
        knobs=knob_count,
    )
    for layer_data in data.get("layers") or []:
        layer = empty_layer(rows, columns, knob_count)
        buttons = layer_data.get("buttons") or []
        for r, row in enumerate(buttons):
            if r >= rows:
                break
            for c, value in enumerate(row or []):
                if c >= columns:
                    break
                layer.buttons[r][c] = _yaml_button_value(value)
        knobs = layer_data.get("knobs") or []
        for index, knob in enumerate(knobs):
            if index >= knob_count:
                break
            if not isinstance(knob, dict):
                continue
            press = knob.get("press")
            if press is None and "gpress" in knob:
                press = knob.get("gpress")
            layer.knobs[index] = Knob(
                ccw=_yaml_button_value(knob.get("ccw")),
                press=_yaml_button_value(press),
                cw=_yaml_button_value(knob.get("cw")),
            )
        mapping.layers.append(layer)
    return mapping


def _yaml_button_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def mapping_to_yaml(mapping: Mapping) -> str:
    lines = [
        f"model: {mapping.model}",
        f"orientation: {mapping.orientation}",
        "",
        f"rows: {mapping.rows}",
        f"columns: {mapping.columns}",
        f"knobs: {mapping.knobs}",
        "",
        "layers:",
    ]
    for layer in mapping.layers:
        lines.append("  - buttons:")
        for row in layer.buttons:
            lines.append(f"      - {_flow_row(row)}")
        lines.append("    knobs:")
        if not layer.knobs:
            lines.append("      []")
        for knob in layer.knobs:
            first = True
            for action in KNOB_ACTIONS:
                value = getattr(knob, action)
                rendered = _yaml_scalar(value)
                if first:
                    lines.append(f"      - {action}: {rendered}")
                    first = False
                else:
                    lines.append(f"        {action}: {rendered}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _flow_row(row: list[str | None]) -> str:
    return "[" + ", ".join(_yaml_scalar(item) for item in row) + "]"


def _yaml_scalar(value: str | None) -> str:
    if value is None:
        return "null"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def mapping_to_text(mapping: Mapping) -> str:
    lines = [
        "# CH57x keypad mapping",
        "#",
        "# Type letters as plain text. Wrap keys and combos in {braces}.",
        "#   Raspberry Pi          types that text",
        "#   {ctrl-c}              Ctrl+C",
        "#   {alt-tab}             Alt+Tab",
        "#   {win-r}cmd{enter}     Win+R, type cmd, Enter",
        "#   {f12} {escape} {delete} {shift}",
        "#   {play} {volumedown} {click}",
        "#",
        "# Empty button or knob action: -",
        "# Literal brace characters: {{ and }}",
        "#",
        f"model: {mapping.model}",
        f"orientation: {mapping.orientation}",
        f"rows: {mapping.rows}",
        f"columns: {mapping.columns}",
        f"knobs: {mapping.knobs}",
        "",
    ]
    for index, layer in enumerate(mapping.layers, start=1):
        lines.append(f"=== Layer {index} ===")
        for r, row in enumerate(layer.buttons, start=1):
            for c, value in enumerate(row, start=1):
                try:
                    rendered = macro_to_text(value)
                except ValueError as exc:
                    rendered = f"[ERROR: {exc}]"
                lines.append(f"[{r},{c}] {rendered}")
        for k, knob in enumerate(layer.knobs, start=1):
            parts = []
            for action in KNOB_ACTIONS:
                try:
                    parts.append(macro_to_text(getattr(knob, action)))
                except ValueError as exc:
                    parts.append(f"[ERROR: {exc}]")
            lines.append(f"knob {k}: {parts[0]} | {parts[1]} | {parts[2]}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def text_to_mapping(text: str, template: Mapping | None = None) -> Mapping:
    base = template or Mapping()
    mapping = Mapping(
        model=base.model,
        orientation=base.orientation,
        rows=base.rows,
        columns=base.columns,
        knobs=base.knobs,
    )
    current: Layer | None = None
    saw_labeled_buttons = False
    legacy_slots: dict[int, list[str | None]] = {}

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        meta_match = re.match(
            r"^(model|orientation|rows|columns|knobs)\s*:\s*(.+)$",
            stripped,
            re.IGNORECASE,
        )
        if meta_match:
            key = meta_match.group(1).lower()
            value = meta_match.group(2).strip()
            if key == "model":
                mapping.model = value
            elif key == "orientation":
                mapping.orientation = value
            elif key == "rows":
                mapping.rows = int(value)
            elif key == "columns":
                mapping.columns = int(value)
            elif key == "knobs":
                mapping.knobs = int(value)
            continue

        layer_match = LAYER_RE.match(stripped)
        if layer_match:
            current = _ensure_layer(mapping, int(layer_match.group(1)))
            continue

        button_match = BUTTON_RE.match(stripped)
        if button_match:
            saw_labeled_buttons = True
            if current is None:
                current = _ensure_layer(mapping, 1)
            row_i = int(button_match.group(1))
            col_i = int(button_match.group(2))
            _set_button(current, mapping, row_i, col_i, button_match.group(3), lineno)
            continue

        knob_action_match = KNOB_ACTION_RE.match(stripped)
        if knob_action_match:
            if current is None:
                current = _ensure_layer(mapping, 1)
            _set_knob_action(
                current,
                mapping,
                int(knob_action_match.group(1)),
                knob_action_match.group(2).lower(),
                knob_action_match.group(3),
                lineno,
            )
            continue

        knob_match = KNOB_LINE_RE.match(stripped)
        if knob_match:
            if current is None:
                current = _ensure_layer(mapping, 1)
            _set_knob_line(
                current, mapping, int(knob_match.group(1)), knob_match.group(2), lineno
            )
            continue

        legacy_match = LEGACY_LINE_RE.match(stripped)
        if legacy_match:
            layer_n = int(legacy_match.group(1))
            payload = legacy_match.group(3)
            legacy_slots.setdefault(layer_n, []).append(_parse_cell(payload, lineno))
            continue

        raise ValueError(f"Line {lineno}: do not understand {stripped!r}")

    if legacy_slots and not saw_labeled_buttons:
        for layer_n, values in sorted(legacy_slots.items()):
            layer = _ensure_layer(mapping, layer_n)
            for index, value in enumerate(values):
                r, c = divmod(index, mapping.columns)
                if r >= mapping.rows:
                    raise ValueError(
                        f"Layer {layer_n} has more buttons than {mapping.rows}x{mapping.columns}"
                    )
                layer.buttons[r][c] = value

    if not mapping.layers:
        mapping.layers.append(empty_layer(mapping.rows, mapping.columns, mapping.knobs))
    return mapping


def _ensure_layer(mapping: Mapping, number: int) -> Layer:
    if number < 1:
        raise ValueError("Layer numbers start at 1")
    while len(mapping.layers) < number:
        mapping.layers.append(
            empty_layer(mapping.rows, mapping.columns, mapping.knobs)
        )
    layer = mapping.layers[number - 1]
    _resize_layer(layer, mapping.rows, mapping.columns, mapping.knobs)
    return layer


def _resize_layer(layer: Layer, rows: int, columns: int, knob_count: int) -> None:
    while len(layer.buttons) < rows:
        layer.buttons.append([None] * columns)
    layer.buttons = layer.buttons[:rows]
    for r, row in enumerate(layer.buttons):
        if len(row) < columns:
            layer.buttons[r] = row + [None] * (columns - len(row))
        else:
            layer.buttons[r] = row[:columns]
    while len(layer.knobs) < knob_count:
        layer.knobs.append(Knob())
    layer.knobs = layer.knobs[:knob_count]


def _parse_cell(value: str, lineno: int) -> str | None:
    try:
        return text_to_macro(value)
    except ValueError as exc:
        raise ValueError(f"Line {lineno}: {exc}") from exc


def _set_button(
    layer: Layer, mapping: Mapping, row: int, column: int, value: str, lineno: int
) -> None:
    if not (1 <= row <= mapping.rows and 1 <= column <= mapping.columns):
        raise ValueError(
            f"Line {lineno}: button [{row},{column}] is outside "
            f"{mapping.rows}x{mapping.columns}"
        )
    layer.buttons[row - 1][column - 1] = _parse_cell(value, lineno)


def _set_knob_line(
    layer: Layer, mapping: Mapping, number: int, value: str, lineno: int
) -> None:
    if not (1 <= number <= mapping.knobs):
        raise ValueError(f"Line {lineno}: knob {number} is outside 1..{mapping.knobs}")
    parts = [part.strip() for part in value.split("|")]
    if len(parts) != 3:
        raise ValueError(
            f"Line {lineno}: knob line must be 'ccw | press | cw' (got {value!r})"
        )
    layer.knobs[number - 1] = Knob(
        ccw=_parse_cell(parts[0], lineno),
        press=_parse_cell(parts[1], lineno),
        cw=_parse_cell(parts[2], lineno),
    )


def _set_knob_action(
    layer: Layer,
    mapping: Mapping,
    number: int,
    action: str,
    value: str,
    lineno: int,
) -> None:
    if not (1 <= number <= mapping.knobs):
        raise ValueError(f"Line {lineno}: knob {number} is outside 1..{mapping.knobs}")
    setattr(layer.knobs[number - 1], action, _parse_cell(value, lineno))


def yaml_to_txt(yaml_path: Path | str, txt_path: Path | str) -> Mapping:
    mapping = load_yaml_mapping(yaml_path)
    Path(txt_path).write_text(mapping_to_text(mapping), encoding="utf-8")
    return mapping


def txt_to_yaml(
    txt_path: Path | str,
    yaml_path: Path | str,
    template_yaml: Path | str | None = None,
) -> Mapping:
    template = load_yaml_mapping(template_yaml) if template_yaml else None
    text = Path(txt_path).read_text(encoding="utf-8")
    mapping = text_to_mapping(text, template)
    Path(yaml_path).write_text(mapping_to_yaml(mapping), encoding="utf-8")
    return mapping
