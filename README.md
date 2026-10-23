# Macro Keyboard

Edit CH57x keypad mappings as plain text, then upload them with [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool).

The keypad firmware cannot be read back. **`macros.yaml` is the current config.** `download` exports that file to `macros.txt` for editing.

## Setup

1. Install [Python 3.10+](https://www.python.org/downloads/).
2. Install this project's dependency:

   ```powershell
   pip install -r requirements.txt
   ```

3. Install the keypad programmer:

   ```powershell
   cargo install ch57x-keyboard-tool
   ```

4. On Windows, also install [UsbDk](https://github.com/daynix/UsbDk/releases) (`UsbDk_1.0.22_x64.msi`) so the tool can talk to the keypad.
5. Plug the keypad in with a USB cable (not Bluetooth) when uploading.

## Everyday loop

```powershell
python converter.py download   # macros.yaml -> macros.txt
# edit macros.txt
python converter.py upload     # macros.txt -> macros.yaml -> keypad
```

`upload` validates the YAML with `ch57x-keyboard-tool` before flashing.

To open Notepad (or `$EDITOR`), then convert and upload when you close it:

```powershell
python converter.py edit
```

## Commands

| Command | What it does |
|---|---|
| `download` | Export `macros.yaml` to `macros.txt` |
| `to-txt` | Same as `download` |
| `to-yaml` | Convert `macros.txt` back to `macros.yaml` (writes `macros.yaml.bak` first) |
| `upload` | Convert `.txt` → `.yaml`, validate, flash the keypad |
| `upload --yaml-only` | Flash the existing YAML without converting |
| `flash` | Upload the existing YAML only |
| `validate` | Convert `.txt` → `.yaml` and validate, no flash |
| `edit` | Download, open an editor, then upload |

Global options:

```powershell
python converter.py --yaml path\to\file.yaml --txt path\to\file.txt <command>
python converter.py --tool C:\path\to\ch57x-keyboard-tool.exe upload
python converter.py edit --editor notepad
```

## Text file format

Each layer is a grid. Buttons are `[row,column]`. Knobs are `ccw | press | cw`.

```
model: ch57x-1
orientation: normal
rows: 3
columns: 4
knobs: 3

=== Layer 1 ===
[1,1] Amicus.44{enter}
[1,2] jon{tab}Amicus.44{enter}
[1,3] Raspberry Pi
[1,4] home{enter}cls{enter}
[3,1] {ctrl-b}
[3,2] {alt-b}
knob 1: {previous} | {play} | {next}
knob 2: {win-left} | {calculator} | {win-right}
knob 3: {volumedown} | {mute} | {volumeup}
```

Rules:

- Letters, digits, spaces, and punctuation are typed as-is. `Hello, world!` types that text.
- Keys, combos, media, and mouse actions go in `{braces}`.
- Mix them freely: `{win-r}cmd{enter}`
- Empty button or knob action: `-`
- Literal `{` or `}` characters: `{{` and `}}`
- `{enter}`, `{tab}`, and `{backspace}` stay on one line. `\n`, `\t`, and `\b` are also accepted.
- The keypad sends QWERTY key presses, not characters. On a non-QWERTY layout, write the key as it is labeled on a US keyboard.

You can also write a knob as three lines:

```
knob 1 ccw: {previous}
knob 1 press: {play}
knob 1 cw: {next}
```

## Special keys

Wrap these in braces. Names are case-insensitive. `{Esc}` and `{escape}` are the same key.

### Editing and navigation

| Key | Token | Aliases |
|---|---|---|
| Enter | `{enter}` | `{return}` |
| Tab | `{tab}` | |
| Backspace | `{backspace}` | |
| Escape | `{escape}` | `{esc}` |
| Space | `{space}` | (or a literal space in a longer string) |
| Delete | `{delete}` | `{del}` |
| Insert | `{insert}` | `{ins}` |
| Home | `{home}` | |
| End | `{end}` | |
| Page Up | `{pageup}` | `{pgup}` |
| Page Down | `{pagedown}` | `{pgdn}`, `{pagedn}` |
| Left | `{left}` | |
| Right | `{right}` | |
| Up | `{up}` | |
| Down | `{down}` | |

### Function keys

`{f1}` through `{f24}`.

### Locks and system keys

`{capslock}` `{numlock}` `{scrolllock}` `{printscreen}` `{pause}` `{application}` `{power}`

### Numpad

`{numpad0}`–`{numpad9}` `{numpadenter}` `{numpaddot}` `{numpadplus}` `{numpadminus}` `{numpadslash}` `{numpadasterisk}` `{numpadequal}`

### Custom HID code

Use a USB usage code when a key has no name: `{<101>}`.

See [HID Usage Tables](https://www.usb.org/sites/default/files/documents/hut1_12v2.pdf) section 10.

## Modifiers and combinations

Join modifiers and a key with hyphens:

```
{ctrl-c}
{alt-tab}
{win-r}
{ctrl-shift-v}
{ctrl-alt-delete}
{shift}
```

| Modifier | Aliases | Meaning |
|---|---|---|
| `ctrl` | `control` | Control |
| `shift` | | Shift |
| `alt` | `opt` | Alt / Option |
| `win` | `cmd`, `super`, `meta` | Windows / Command |
| `rctrl` | | Right Control |
| `rshift` | | Right Shift |
| `ralt` | `ropt` | Right Alt / Option |
| `rwin` | `rcmd` | Right Windows / Command |

A modifier by itself is valid: `{shift}` or `{ctrl-alt}`.

Sequences are one action after another. The keypad allows up to five pieces:

```
{ctrl-a}{ctrl-c}          select all, then copy
{win-r}cmd{enter}         open Run and type cmd
{alt-tab}                 switch window
```

On 3×1 + 1 knob pads, modifiers only work on the first key in a sequence.

## Media keys

Use a single `{token}` for the whole button or knob action. Do not mix media keys with typed text.

| Token | Action |
|---|---|
| `{play}` | Play / pause |
| `{next}` | Next track |
| `{previous}` | Previous track (`{prev}` also works) |
| `{stop}` | Stop |
| `{mute}` | Mute |
| `{volumeup}` | Volume up |
| `{volumedown}` | Volume down |
| `{calculator}` | Open calculator |
| `{favorites}` | Open favorites |
| `{screenlock}` | Lock the screen |
| `{screenbrightnessup}` | Brightness up |
| `{screenbrightnessdown}` | Brightness down |
| `{webpagehome}` | Browser home |
| `{webpageback}` | Browser back |
| `{webpageforward}` | Browser forward |

## Mouse actions

Also a single `{token}` for the whole action. Mouse modifiers are only `ctrl`, `shift`, and `alt` (no Win).

| Token | Action |
|---|---|
| `{click}` | Left click (`{lclick}` is the same) |
| `{rclick}` | Right click |
| `{mclick}` | Middle click |
| `{click(left)}` | Left click |
| `{click(left+right)}` | Two buttons at once |
| `{ctrl-click}` | Click while holding Ctrl |
| `{move(10,0)}` | Move 10px right, 0px down (range -128..127) |
| `{drag(left,10,0)}` | Drag with the left button |
| `{wheelup}` / `{wheeldown}` | Scroll (`{wheel(1)}` / `{wheel(-1)}`) |
| `{ctrl-wheelup}` | Often zooms |

## Examples

```
[1,1] Hello{enter}
[1,2] {ctrl-c}
[1,3] {alt-tab}
[1,4] {win-r}notepad{enter}
[2,1] {f12}
[2,2] {ctrl-alt-delete}
[2,3] {play}
[2,4] {click}
[3,1] -
knob 1: {volumedown} | {mute} | {volumeup}
```

That last button is empty. The knob turns volume down, click mutes, turn the other way volume up.

## Files

| File | Role |
|---|---|
| `macros.txt` | What you edit |
| `macros.yaml` | Last known keypad config; generated from the `.txt` |
| `macros.yaml.bak` | Previous YAML, written just before each convert |
| `converter.py` | CLI |
| `macro_parser.py` | YAML ↔ text conversion |

If `ch57x-keyboard-tool` is not on `PATH`, it is also looked up in `%USERPROFILE%\.cargo\bin`.
