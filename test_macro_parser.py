import unittest

from macro_parser import (
    macro_to_text,
    mapping_to_text,
    mapping_to_yaml,
    parse_macro,
    text_to_macro,
    text_to_mapping,
)


class MacroRoundTripTests(unittest.TestCase):
    def assert_yaml_text(self, yaml_macro: str, text: str) -> None:
        self.assertEqual(macro_to_text(yaml_macro), text)
        self.assertEqual(text_to_macro(text), parse_macro(yaml_macro).to_yaml())

    def test_typed_sentence(self):
        yaml_macro = "shift-a,m,i,c,u,s,dot,4,4,enter"
        self.assert_yaml_text(yaml_macro, "Amicus.44{enter}")

    def test_space_and_tab(self):
        self.assert_yaml_text(
            "j,o,n,tab,shift-a,m,i,c,u,s,dot,4,4,enter",
            "jon{tab}Amicus.44{enter}",
        )
        self.assert_yaml_text(
            "shift-r,a,s,p,b,e,r,r,y,space,shift-p,i",
            "Raspberry Pi",
        )

    def test_legacy_escapes(self):
        self.assertEqual(text_to_macro("home\\ncls\\n"), "h,o,m,e,enter,c,l,s,enter")

    def test_modifier_combos(self):
        self.assert_yaml_text("ctrl-b", "{ctrl-b}")
        self.assert_yaml_text("alt-b", "{alt-b}")
        self.assert_yaml_text("ctrl-alt-delete", "{ctrl-alt-delete}")
        self.assert_yaml_text("ctrl-shift-a", "{ctrl-shift-a}")
        self.assert_yaml_text("win-r", "{win-r}")
        self.assertEqual(text_to_macro("{cmd-v}"), "win-v")
        self.assertEqual(text_to_macro("{opt-tab}"), "alt-tab")

    def test_mixed_sequence(self):
        self.assert_yaml_text("win-r,c,m,d,enter", "{win-r}cmd{enter}")

    def test_special_keys(self):
        self.assert_yaml_text("escape", "{escape}")
        self.assert_yaml_text("f1", "{f1}")
        self.assert_yaml_text("delete", "{delete}")
        self.assert_yaml_text("backspace", "{backspace}")
        self.assert_yaml_text("shift", "{shift}")
        self.assertEqual(text_to_macro("{esc}"), "escape")
        self.assertEqual(text_to_macro("{del}"), "delete")

    def test_media_and_mouse(self):
        self.assert_yaml_text("play", "{play}")
        self.assert_yaml_text("Previous", "{previous}")
        self.assert_yaml_text("ctrl-click", "{ctrl-click}")
        self.assert_yaml_text("move(0,10)", "{move(0,10)}")
        self.assertEqual(text_to_macro("{prev}"), "previous")

    def test_delay(self):
        self.assert_yaml_text("{delay(100)}left,a", "{delay(100)}{left}a")

    def test_empty(self):
        self.assertEqual(macro_to_text(None), "-")
        self.assertIsNone(text_to_macro("-"))
        self.assertIsNone(text_to_macro(""))

    def test_literal_braces(self):
        self.assertEqual(text_to_macro("{{hi}}"), "shift-leftbracket,h,i,shift-rightbracket")

    def test_media_cannot_mix(self):
        with self.assertRaises(ValueError):
            text_to_macro("hello{play}")


class MappingFileTests(unittest.TestCase):
    def test_labeled_round_trip(self):
        text = """
model: ch57x-1
orientation: normal
rows: 1
columns: 2
knobs: 1

=== Layer 1 ===
[1,1] {ctrl-c}
[1,2] Hello{enter}
knob 1: {volumedown} | {mute} | {volumeup}
"""
        mapping = text_to_mapping(text)
        self.assertEqual(mapping.layers[0].buttons[0][0], "ctrl-c")
        self.assertEqual(mapping.layers[0].buttons[0][1], "shift-h,e,l,l,o,enter")
        self.assertEqual(mapping.layers[0].knobs[0].press, "mute")

        again = text_to_mapping(mapping_to_text(mapping))
        self.assertEqual(mapping_to_yaml(mapping), mapping_to_yaml(again))

    def test_legacy_format(self):
        text = """
rows: 2
columns: 2
knobs: 0

Layer 1, 1. {ctrl-b}
Layer 1, 2. hi
Layer 1, 3. {f1}
Layer 1, 4. -
"""
        mapping = text_to_mapping(text)
        self.assertEqual(mapping.layers[0].buttons[0][0], "ctrl-b")
        self.assertEqual(mapping.layers[0].buttons[0][1], "h,i")
        self.assertEqual(mapping.layers[0].buttons[1][0], "f1")
        self.assertIsNone(mapping.layers[0].buttons[1][1])


if __name__ == "__main__":
    unittest.main()
