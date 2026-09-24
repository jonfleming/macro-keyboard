import string
import yaml

# Mapping from key names (lowercase) to (unshifted, shifted) characters
KEY_MAP = {}

# Letters
for letter in string.ascii_lowercase:
    KEY_MAP[letter] = (letter, letter.upper())

# Digits
KEY_MAP['0'] = ('0', ')')
KEY_MAP['1'] = ('1', '!')
KEY_MAP['2'] = ('2', '@')
KEY_MAP['3'] = ('3', '#')
KEY_MAP['4'] = ('4', '$')
KEY_MAP['5'] = ('5', '%')
KEY_MAP['6'] = ('6', '^')
KEY_MAP['7'] = ('7', '&')
KEY_MAP['8'] = ('8', '*')
KEY_MAP['9'] = ('9', '(')

# Punctuation and specials
KEY_MAP['space'] = (' ', ' ')
KEY_MAP['dot'] = ('.', '>')
KEY_MAP['comma'] = (',', '<')
KEY_MAP['slash'] = ('/', '?')
KEY_MAP['semicolon'] = (';', ':')
KEY_MAP['quote'] = ("'", '"')
KEY_MAP['grave'] = ('`', '~')
KEY_MAP['minus'] = ('-', '_')
KEY_MAP['equal'] = ('=', '+')
KEY_MAP['leftbracket'] = ('[', '{')
KEY_MAP['rightbracket'] = (']', '}')
KEY_MAP['backslash'] = ('\\', '|')
KEY_MAP['enter'] = ('\\n', '\\n')
KEY_MAP['tab'] = ('\\t', '\\t')
KEY_MAP['backspace'] = ('\\b', '\\b')

# Reverse mapping: char to accord string
# Note: specials use capitalized names to match the example (e.g., "Space", "Dot")
CHAR_TO_ACCORD = {}
for name, (unshifted, shifted) in KEY_MAP.items():
    display_name = name if name.isalpha() or name.isdigit() else name.capitalize()
    CHAR_TO_ACCORD[unshifted] = display_name
    if shifted != unshifted:
        CHAR_TO_ACCORD[shifted] = f"shift-{display_name}"

# Overwrite specials if needed (e.g., Enter not capitalized in map but in enum it is)
CHAR_TO_ACCORD['\n'] = 'Enter'
CHAR_TO_ACCORD['\t'] = 'Tab'
CHAR_TO_ACCORD['\b'] = 'Backspace'

def text_to_macro(text: str) -> str:
    """
    Convert a string like "Raspberry Pi." to a comma-separated macro like
    "shift-r,a,s,p,b,e,r,r,y,Space,shift-p,i,Dot".
    Raises ValueError for unsupported characters.
    """
    accords = []
    i = 0
    while i < len(text):
        c = text[i]
        # Handle escaped newlines and tabs as single characters
        if c == '\\' and i + 1 < len(text):
            next_c = text[i + 1]
            if next_c == 'n':
                c = '\n'
                i += 1
            elif next_c == 't':
                c = '\t'
                i += 1
            elif next_c == 'b':
                c = '\b'
                i += 1
        if c in CHAR_TO_ACCORD:
            accords.append(CHAR_TO_ACCORD[c])
        else:
            raise ValueError(f"Unsupported character: {c}")
        i += 1
    return ','.join(accords)

def macro_to_text(macro_str: str) -> str:
    """
    Convert a comma-separated macro like "h,o,m,e,Enter,c,l,s,Enter" to a string like "home\ncls\n".
    Supports shift modifier for shifted characters. Ignores other modifiers.
    Handles backspace by removing the previous character.
    Raises ValueError for unsupported key codes or complex modifiers.
    """
    result = ''
    parts = macro_str.split(',')
    for part in parts:
        if not part.strip():
            continue
        subparts = part.split('-')
        mods = {m.lower() for m in subparts[:-1]}
        code_name = subparts[-1].lower()

        if 'ctrl' in mods or 'alt' in mods or 'win' in mods or 'rctrl' in mods or 'ralt' in mods or 'rwin' in mods:
            raise ValueError(f"Unsupported modifier in accord: {part}")

        has_shift = 'shift' in mods or 'rshift' in mods

        if code_name not in KEY_MAP:
            raise ValueError(f"Unsupported key code: {code_name}")

        idx = 1 if has_shift else 0
        char = KEY_MAP[code_name][idx]

        if char == '\b':
            if result:
                result = result[:-1]
        else:
            result += char
    return result

# --- Conversion utilities ---
def yaml_to_txt(yaml_path: str, txt_path: str):
    """
    Reads macros from a YAML file with layers/buttons structure, converts each macro string to text, and writes to a text file.
    Processes all layers' buttons.
    """
    with open(yaml_path, 'r') as yf:
        data = yaml.safe_load(yf)
    layers = data.get('layers', [])
    if not layers:
        raise ValueError("No layers found in YAML file.")
    macros = []
    for layer_idx, layer in enumerate(layers):
        buttons_matrix = layer.get('buttons', [])
        for row in buttons_matrix:
            for macro_str in row:
                macros.append((layer_idx, macro_str))
    with open(txt_path, 'w') as tf:
        for i, (layer_idx, macro_str) in enumerate(macros, 1):
            try:
                text = macro_to_text(macro_str)
            except Exception as e:
                text = f"[ERROR: {e}]"
            tf.write(f"Layer {layer_idx+1}, {i}. {text}\n")

def txt_to_yaml(txt_path: str, yaml_path: str):
    """
    Reads macro lines from a text file, converts each to macro string, and writes to a YAML file (list).
    Updates all layers' buttons.
    """
    # Read macros from text file
    macros = []
    with open(txt_path, 'r') as tf:
        for line in tf:
            line = line.strip()
            print(line, end='')
            if not line:
                continue
            # Try to extract layer info if present
            if line.startswith('Layer '):
                parts = line.split(',', 1)
                if len(parts) == 2:
                    line = parts[1].strip()
                    if '. ' in line:
                        line = line.split('. ', 1)[1].strip()
            elif '. ' in line:
                line = line.split('. ', 1)[1].strip()
            macro_str = text_to_macro(line)
            print(f" => {macro_str}")
            macros.append(macro_str)

    # Load original YAML to preserve metadata and knobs
    import yaml
    with open('macros.yaml', 'r') as yf:
        orig_yaml = yaml.safe_load(yf)
    rows = orig_yaml.get('rows', 3)
    cols = orig_yaml.get('columns', 4)
    layers = orig_yaml.get('layers', [])
    # Rebuild the buttons matrix for all layers
    new_layers = []
    macro_idx = 0
    for layer in layers:
        matrix = []
        buttons_matrix = layer.get('buttons', [])
        for r in range(len(buttons_matrix)):
            row_macros = []
            for c in range(len(buttons_matrix[r])):
                if macro_idx < len(macros):
                    row_macros.append(macros[macro_idx])
                    macro_idx += 1
                else:
                    row_macros.append(buttons_matrix[r][c])
            matrix.append(row_macros)
        new_layers.append({
            'buttons': matrix,
            'knobs': layer.get('knobs', [])
        })

    # Write YAML manually to ensure button rows are flow-style lists of quoted strings
    def quoted_flow_list(lst):
        return '[' + ', '.join(f'"{item}"' for item in lst) + ']'

    with open(yaml_path, 'w') as yf:
        # Top-level keys
        yf.write(f'orientation: {orig_yaml["orientation"]}\n')
        
        yf.write('\n')
        yf.write(f'rows: {orig_yaml["rows"]}\n')
        yf.write(f'columns: {orig_yaml["columns"]}\n')
        yf.write(f'knobs: {orig_yaml["knobs"]}\n')
        
        yf.write('\n')
        yf.write('layers:\n')
        for layer in new_layers:
            yf.write('  - buttons:\n')
            for row in layer['buttons']:
                yf.write(f'      - {quoted_flow_list(row)}\n')
            yf.write('    knobs:\n')
            for knob in layer['knobs']:
                for k, v in knob.items():
                    yf.write(f'      - {k}: "{v}"\n' if k == "ccw" else f'        {k}: "{v}"\n')
            yf.write('\n')

def main():
    text = "Amicus.44\n"
    macro = text_to_macro(text)
    print(f"Macro: {macro}")
    converted_back = macro_to_text(macro)
    print(f"Converted back: {converted_back}")

if __name__ == "__main__":
    main()