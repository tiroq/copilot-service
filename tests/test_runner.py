import unittest

from copilot_service.providers.base import Provider, ProviderResult
from copilot_service.runner import run_bridge_request


class _StaticProvider(Provider):
    name = "static"

    def __init__(self, result: ProviderResult):
        self._result = result

    def ask(self, prompt: str, model: str, options: dict[str, object]) -> ProviderResult:
        return self._result


class RunnerTests(unittest.TestCase):
    def test_route_topic_provider_failure_is_not_ok(self):
        request = {
            "task": "route-topic",
            "input": {
                "topics": {"asr": {"topic": "AI/ASR", "path": "2_Areas/ai-systems", "aliases": ["asr"]}},
                "fallback_key": "fallback",
            },
            "options": {"fallback_on_invalid": True},
        }
        provider = _StaticProvider(
            ProviderResult(
                ok=False,
                raw_text="not-json",
                error="provider timeout",
            )
        )

        response = run_bridge_request(request, provider=provider)
        self.assertFalse(response["ok"])
        self.assertEqual(response["content"]["decision"], "fallback")
        self.assertTrue(any(err["code"] == "provider_error" for err in response["errors"]))

    def test_route_topic_invalid_output_with_successful_provider_can_fallback_ok(self):
        request = {
            "task": "route-topic",
            "input": {
                "topics": {"asr": {"topic": "AI/ASR", "path": "2_Areas/ai-systems", "aliases": ["asr"]}},
                "fallback_key": "fallback",
            },
            "options": {"fallback_on_invalid": True},
        }
        provider = _StaticProvider(ProviderResult(ok=True, raw_text="not-json"))

        response = run_bridge_request(request, provider=provider)
        self.assertTrue(response["ok"])
        self.assertEqual(response["content"]["decision"], "fallback")


if __name__ == "__main__":
    unittest.main()
