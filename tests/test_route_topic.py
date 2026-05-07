import unittest

from copilot_service.tasks.route_topic import parse_output


class RouteTopicTests(unittest.TestCase):
    def setUp(self):
        self.task_input = {
            "topics": {
                "asr": {"topic": "AI/ASR", "path": "2_Areas/ai-systems", "aliases": ["whisper"]},
            },
            "fallback_key": "fallback",
        }

    def test_valid_output(self):
        ok, content, errors = parse_output(
            '{"decision":"asr","confidence":0.87,"reason":"matches alias"}',
            self.task_input,
            {},
        )
        self.assertTrue(ok)
        self.assertEqual(content["decision"], "asr")
        self.assertEqual(content["confidence"], 0.87)
        self.assertEqual(errors, [])

    def test_confidence_clamped(self):
        ok, content, _ = parse_output(
            '{"decision":"asr","confidence":10,"reason":"high"}',
            self.task_input,
            {},
        )
        self.assertTrue(ok)
        self.assertEqual(content["confidence"], 1.0)

    def test_invalid_output_falls_back(self):
        ok, content, errors = parse_output("bad output", self.task_input, {})
        self.assertTrue(ok)
        self.assertEqual(content["decision"], "fallback")
        self.assertEqual(errors[0]["code"], "invalid_provider_output")

    def test_invalid_output_without_fallback(self):
        ok, content, errors = parse_output("bad", self.task_input, {"fallback_on_invalid": False})
        self.assertFalse(ok)
        self.assertEqual(content, {})
        self.assertEqual(errors[0]["code"], "invalid_provider_output")


if __name__ == "__main__":
    unittest.main()
