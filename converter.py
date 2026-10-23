#!/usr/bin/env python3
"""CLI for editing CH57x keypad mappings as plain text."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from macro_parser import txt_to_yaml, yaml_to_txt

ROOT = Path(__file__).resolve().parent
DEFAULT_YAML = ROOT / "macros.yaml"
DEFAULT_TXT = ROOT / "macros.txt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="converter.py",
        description=(
            "Edit CH57x keypad mappings as plain text, then upload them.\n\n"
            "The keypad firmware cannot be read back. Local macros.yaml is the\n"
            "current config. Typical loop:\n"
            "  python converter.py download   # yaml -> txt\n"
            "  # edit macros.txt\n"
            "  python converter.py upload     # txt -> yaml -> keypad"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--yaml",
        type=Path,
        default=DEFAULT_YAML,
        help=f"YAML mapping (default: {DEFAULT_YAML.name})",
    )
    parser.add_argument(
        "--txt",
        type=Path,
        default=DEFAULT_TXT,
        help=f"Text mapping (default: {DEFAULT_TXT.name})",
    )
    parser.add_argument(
        "--tool",
        default=None,
        help="Path to ch57x-keyboard-tool (default: search PATH)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "download",
        help="Export the current YAML config to an editable .txt file",
    )
    sub.add_parser("to-txt", help="Convert YAML to text (same as download)")
    sub.add_parser("to-yaml", help="Convert the edited .txt file back to YAML")
    upload = sub.add_parser(
        "upload",
        help="Convert .txt to YAML and flash it to the keypad",
    )
    upload.add_argument(
        "--yaml-only",
        action="store_true",
        help="Upload the existing YAML without converting from .txt first",
    )
    sub.add_parser("flash", help="Upload the existing YAML file only")
    edit = sub.add_parser(
        "edit",
        help="Export, open the .txt file in an editor, then upload",
    )
    edit.add_argument(
        "--editor",
        help="Editor command (default: $EDITOR, or notepad on Windows)",
    )
    sub.add_parser("validate", help="Convert .txt to YAML and validate it")

    args = parser.parse_args(argv)
    try:
        return run(args)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def run(args: argparse.Namespace) -> int:
    yaml_path = args.yaml
    txt_path = args.txt

    if args.command in {"download", "to-txt"}:
        return cmd_download(yaml_path, txt_path)
    if args.command == "to-yaml":
        return cmd_to_yaml(txt_path, yaml_path)
    if args.command == "upload":
        if not args.yaml_only:
            cmd_to_yaml(txt_path, yaml_path)
        return cmd_flash(yaml_path, args.tool)
    if args.command == "flash":
        return cmd_flash(yaml_path, args.tool)
    if args.command == "edit":
        return cmd_edit(yaml_path, txt_path, args.tool, args.editor)
    if args.command == "validate":
        cmd_to_yaml(txt_path, yaml_path)
        return cmd_validate(yaml_path, args.tool)
    raise ValueError(f"Unknown command: {args.command}")


def cmd_download(yaml_path: Path, txt_path: Path) -> int:
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"{yaml_path} not found. This file is the current keypad config "
            "(the device cannot be read back)."
        )
    yaml_to_txt(yaml_path, txt_path)
    print(
        "The keypad firmware cannot be read back; using the last known local config."
    )
    print(f"Exported {yaml_path.name} -> {txt_path}")
    print(f"Edit {txt_path.name}, then run: python converter.py upload")
    return 0


def cmd_to_yaml(txt_path: Path, yaml_path: Path) -> int:
    if not txt_path.exists():
        raise FileNotFoundError(f"{txt_path} not found. Run download first.")
    template = yaml_path if yaml_path.exists() else None
    if yaml_path.exists():
        backup = yaml_path.with_suffix(yaml_path.suffix + ".bak")
        shutil.copy2(yaml_path, backup)
    txt_to_yaml(txt_path, yaml_path, template)
    print(f"Converted {txt_path.name} -> {yaml_path}")
    return 0


def cmd_validate(yaml_path: Path, tool: str | None) -> int:
    exe = find_keyboard_tool(tool)
    subprocess.run([str(exe), "validate", str(yaml_path)], check=True)
    return 0


def cmd_flash(yaml_path: Path, tool: str | None) -> int:
    if not yaml_path.exists():
        raise FileNotFoundError(f"{yaml_path} not found.")
    exe = find_keyboard_tool(tool)
    print(f"Validating {yaml_path.name}...")
    subprocess.run([str(exe), "validate", str(yaml_path)], check=True)
    print(f"Uploading {yaml_path.name} to the keypad...")
    subprocess.run([str(exe), "upload", str(yaml_path)], check=True)
    print("Upload complete.")
    return 0


def cmd_edit(
    yaml_path: Path, txt_path: Path, tool: str | None, editor: str | None
) -> int:
    cmd_download(yaml_path, txt_path)
    command = editor or os.environ.get("EDITOR")
    if command:
        subprocess.run([*command.split(), str(txt_path)], check=True)
    elif os.name == "nt":
        subprocess.run(["notepad.exe", str(txt_path)], check=True)
    else:
        print(f"Open and edit {txt_path}, then re-run: python converter.py upload")
        return 0
    print("Editor closed. Converting and uploading...")
    cmd_to_yaml(txt_path, yaml_path)
    return cmd_flash(yaml_path, tool)


def find_keyboard_tool(explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise FileNotFoundError(f"ch57x-keyboard-tool not found: {path}")
        return path

    for name in ("ch57x-keyboard-tool", "ch57x-keyboard-tool.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)

    cargo_bin = Path.home() / ".cargo" / "bin"
    for name in ("ch57x-keyboard-tool.exe", "ch57x-keyboard-tool"):
        candidate = cargo_bin / name
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "ch57x-keyboard-tool not found on PATH. Install it with "
        "`cargo install ch57x-keyboard-tool` or pass --tool."
    )


if __name__ == "__main__":
    sys.exit(main())
