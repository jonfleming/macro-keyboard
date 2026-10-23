import tempfile
import unittest
from pathlib import Path

from keypad_gui import (
    KeypadApp,
    cell_text,
    clip_lines,
    compute_layout,
    pretty_macro,
    wrap_atoms,
)
from macro_parser import text_to_macro, text_to_mapping

ROOT = Path(__file__).resolve().parent


class PrettyMacroTests(unittest.TestCase):
    def test_typed_text_and_keys(self):
        self.assertEqual(pretty_macro("-"), "")
        self.assertEqual(pretty_macro(""), "")
        self.assertEqual(pretty_macro("Raspberry Pi"), "Raspberry Pi")
        self.assertEqual(pretty_macro("Amicus.44{enter}"), "Amicus.44 ↵")
        self.assertEqual(pretty_macro("jon{tab}Amicus.44{enter}"), "jon ⇥ Amicus.44 ↵")
        self.assertEqual(pretty_macro("home{enter}cls{enter}"), "home ↵ cls ↵")

    def test_combos_and_knobs(self):
        self.assertEqual(pretty_macro("{ctrl-c}"), "Ctrl+C")
        self.assertEqual(pretty_macro("{ctrl-shift-alt-f1}"), "Ctrl+Shift+Alt+F1")
        self.assertEqual(pretty_macro("{win-r}cmd{enter}"), "Win+R cmd ↵")
        self.assertEqual(pretty_macro("{win-left}"), "Win+←")
        self.assertEqual(pretty_macro("{volumedown}"), "Vol −")
        self.assertEqual(pretty_macro("{play}"), "Play")
        self.assertEqual(pretty_macro("{{"), "{")
        self.assertEqual(pretty_macro("{delay(100)}{left}a"), "100ms ← a")

    def test_wrap_breaks_after_plus(self):
        lines = wrap_atoms("Ctrl+Shift+Alt+F1", 11, len)
        self.assertEqual(lines, ["Ctrl+Shift+", "Alt+F1"])
        clipped = clip_lines(["one", "two", "three"], 2, len, 8)
        self.assertEqual(clipped, ["one", "two…"])
        self.assertEqual(
            wrap_atoms("Raspberry Pi", 6, len, break_words=False),
            ["Raspberry", "Pi"],
        )
        self.assertEqual(wrap_atoms("home ↵ cls ↵", 11, len), ["home ↵", "cls ↵"])


class LayoutTests(unittest.TestCase):
    def test_twelve_keys_and_three_knobs_do_not_overlap(self):
        layout = compute_layout(760, 680, 3, 4, 3)
        self.assertEqual(len(layout.keys), 12)
        self.assertEqual(len(layout.knobs), 3)
        self.assertGreater(layout.knobs[2].radius, layout.knobs[0].radius)
        self.assertLess(layout.keys[0].box[0], layout.keys[1].box[0])
        self.assertLess(layout.keys[0].box[1], layout.keys[4].box[1])

        rects = [key.box for key in layout.keys]
        for knob in layout.knobs:
            rects.extend(knob.pills.values())
            bottom = knob.center[1] + knob.radius
            top = min(box[1] for box in knob.pills.values())
            self.assertLess(bottom, top - 4)
        for index, box in enumerate(rects):
            for other in rects[index + 1 :]:
                self.assertFalse(_overlap(box, other), (box, other))


class EditorTests(unittest.TestCase):
    def test_loads_current_mapping_and_saves_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            txt = folder / "macros.txt"
            yaml_path = folder / "macros.yaml"
            txt.write_text((ROOT / "macros.txt").read_text(encoding="utf-8"), encoding="utf-8")
            app = KeypadApp(txt, yaml_path, show=False)
            app.select(("button", 0, 0))
            self.assertEqual(app.editor.get("1.0", "end-1c"), "Amicus.44{enter}")
            app.update_idletasks()
            app.redraw()
            box = next(spot.box for spot in app.hotspots if spot.target == ("button", 0, 0))
            self.assertEqual(
                app.hit((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
                ("button", 0, 0),
            )
            app.select(("knob", 2, "press"))
            self.assertEqual(app.editor.get("1.0", "end-1c"), "{mute}")
            self.assertEqual(cell_text(app.get_binding(("button", 2, 0))), "{ctrl-b}")

            app.select(("button", 0, 3))
            app.set_editor_text("Hello{enter}")
            self.assertTrue(app.apply_editor())
            self.assertTrue(app.save_to_disk())
            saved = text_to_mapping(txt.read_text(encoding="utf-8"))
            self.assertEqual(saved.layers[0].buttons[0][3], text_to_macro("Hello{enter}"))
            self.assertEqual(saved.layers[0].knobs[2].press, "mute")

            app.set_editor_text("{unclosed")
            self.assertFalse(app.apply_editor())
            self.assertTrue(app._invalid)
            app.destroy()


def _overlap(a, b) -> bool:
    return a[0] < b[2] - 0.5 and a[2] > b[0] + 0.5 and a[1] < b[3] - 0.5 and a[3] > b[1] + 0.5


if __name__ == "__main__":
    unittest.main()
