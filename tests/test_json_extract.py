import unittest

from copilot_service.utils.json_extract import extract_json_value


class JsonExtractTests(unittest.TestCase):
    def test_raw_json(self):
        self.assertEqual(extract_json_value('{"a":1}'), {"a": 1})

    def test_fenced_json(self):
        text = """here\n```json\n{\"a\":2}\n```"""
        self.assertEqual(extract_json_value(text), {"a": 2})

    def test_prose_with_json(self):
        text = "Answer: {\"decision\":\"asr\",\"confidence\":0.9,\"reason\":\"fit\"} done"
        self.assertEqual(extract_json_value(text)["decision"], "asr")

    def test_nested_braces(self):
        text = "before {\"outer\": {\"inner\": [1,2,3]}} after"
        self.assertEqual(extract_json_value(text)["outer"]["inner"], [1, 2, 3])

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            extract_json_value("not json")

    def test_bullet_prefix(self):
        """Copilot CLI may prefix output with '● '."""
        self.assertEqual(extract_json_value('\u25cf {"ok":true}'), {"ok": True})

    def test_bullet_prefix_with_spaces(self):
        self.assertEqual(extract_json_value('  \u25cf   {"decision":"asr"}'), {"decision": "asr"})

    def test_fenced_json_triple_backtick(self):
        text = '```json\n{"ok":true}\n```'
        self.assertEqual(extract_json_value(text), {"ok": True})

    def test_text_before_and_after_json(self):
        text = 'Some prefix text {"ok":true} some suffix text'
        self.assertEqual(extract_json_value(text), {"ok": True})

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            extract_json_value("")


if __name__ == "__main__":
    unittest.main()
