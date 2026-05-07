import unittest

from copilot_service.providers.shell import ShellProvider


class ShellProviderTests(unittest.TestCase):
    def test_shell_provider_runs_command(self):
        provider = ShellProvider("python -c \"import sys; print(sys.stdin.read().strip())\"", timeout_seconds=5)
        result = provider.ask("hello", model="gpt-5-mini", options={})
        self.assertTrue(result.ok)
        self.assertEqual(result.raw_text.strip(), "hello")


if __name__ == "__main__":
    unittest.main()
