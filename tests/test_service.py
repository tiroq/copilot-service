"""Tests for copilot_service.service module."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from copilot_service.service import (
    _REJECT_SUBSTRINGS,
    build_env_file,
    build_unit_file,
    detect_copilot_bin,
    validate_copilot_candidate,
    _run_smoke_test,
)


# ---------------------------------------------------------------------------
# validate_copilot_candidate
# ---------------------------------------------------------------------------


class ValidateCopilotCandidateTests(unittest.TestCase):
    def _mock_run(self, stdout: str, returncode: int = 0):
        return MagicMock(stdout=stdout, stderr="", returncode=returncode)

    def _patch_exists(self):
        """Pretend /fake/copilot is an executable file."""
        return (
            patch.object(Path, "is_file", return_value=True),
            patch("os.access", return_value=True),
        )

    def test_accepts_plain_ok_json(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run('{"ok":true}')):
            self.assertTrue(validate_copilot_candidate("/fake/copilot"))

    def test_accepts_bullet_prefix(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run('● {"ok":true}')):
            self.assertTrue(validate_copilot_candidate("/fake/copilot"))

    def test_accepts_bullet_with_spaces(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run('  ●   {"ok":true}  ')):
            self.assertTrue(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_installer_prompt(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run(
            "Install GitHub Copilot CLI? ['y/N'] \nchanged 2 packages in 2s"
        )):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_changed_packages(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run("changed 2 packages in 2s")):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_unknown_option(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run("error: unknown option --silent")):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_unknown_command(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run("error: unknown command 'ask'")):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_non_ok_json(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run('{"ok":false}')):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_timeout(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", side_effect=subprocess.TimeoutExpired("/fake/copilot", 20)):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_nonexistent_file(self):
        self.assertFalse(validate_copilot_candidate("/definitely/does/not/exist"))

    def test_rejects_oserror(self):
        with patch("os.access", return_value=True), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("subprocess.run", side_effect=OSError("permission denied")):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))

    def test_rejects_empty_output(self):
        p1, p2 = self._patch_exists()
        with p1, p2, patch("subprocess.run", return_value=self._mock_run("")):
            self.assertFalse(validate_copilot_candidate("/fake/copilot"))


# ---------------------------------------------------------------------------
# detect_copilot_bin — detection order
# ---------------------------------------------------------------------------


class DetectCopilotBinTests(unittest.TestCase):
    def _make_valid(self, path: str):
        """Patch validate_copilot_candidate to return True for *path* only."""
        def _validator(p, model="gpt-5-mini", timeout_seconds=20):
            return p == path
        return patch("copilot_service.service.validate_copilot_candidate", side_effect=_validator)

    def _patch_exist(self, paths: list[str]):
        """Patch Path.is_file and os.access to pretend only *paths* exist."""
        def _is_file(self_path):
            return str(self_path) in paths
        def _access(p, mode):
            return str(p) in paths
        return (
            patch.object(Path, "is_file", _is_file),
            patch("os.access", _access),
        )

    def test_explicit_copilot_bin_takes_priority(self):
        explicit = "/custom/copilot"
        with self._make_valid(explicit), \
             patch.object(Path, "is_file", return_value=True), \
             patch("os.access", return_value=True):
            result = detect_copilot_bin(explicit=explicit)
        self.assertEqual(result, explicit)

    def test_env_copilot_cli_takes_priority_over_local_bin(self):
        env_bin = "/env/copilot"
        local_bin = str(Path.home() / ".local" / "bin" / "copilot")
        with self._make_valid(env_bin), \
             patch.object(Path, "is_file", return_value=True), \
             patch("os.access", return_value=True), \
             patch.dict(os.environ, {"COPILOT_CLI": env_bin}):
            result = detect_copilot_bin()
        self.assertEqual(result, env_bin)

    def test_local_bin_before_vscode_server(self):
        local = str(Path.home() / ".local" / "bin" / "copilot")
        vscode = str(
            Path.home() / ".vscode-server" / "data" / "User" / "globalStorage"
            / "github.copilot-chat" / "copilotCli" / "copilot"
        )
        with self._make_valid(local), \
             patch.object(Path, "is_file", return_value=True), \
             patch("os.access", return_value=True), \
             patch.dict(os.environ, {}, clear=False):
            # Remove COPILOT_CLI if set
            env = {k: v for k, v in os.environ.items() if k != "COPILOT_CLI"}
            with patch.dict(os.environ, env, clear=True):
                result = detect_copilot_bin()
        self.assertEqual(result, local)

    def test_returns_none_when_all_fail(self):
        with patch("copilot_service.service.validate_copilot_candidate", return_value=False), \
             patch.object(Path, "is_file", return_value=False), \
             patch("os.access", return_value=False), \
             patch("shutil.which", return_value=None), \
             patch("subprocess.run", return_value=MagicMock(stdout="", returncode=1)), \
             patch.dict(os.environ, {}, clear=True):
            result = detect_copilot_bin()
        self.assertIsNone(result)

    def test_explicit_invalid_raises_systemexit(self):
        with patch("copilot_service.service.validate_copilot_candidate", return_value=False), \
             patch.object(Path, "is_file", return_value=True), \
             patch("os.access", return_value=True):
            with self.assertRaises(SystemExit):
                detect_copilot_bin(explicit="/bad/copilot")

    def test_env_invalid_raises_systemexit(self):
        with patch("copilot_service.service.validate_copilot_candidate", return_value=False), \
             patch.object(Path, "is_file", return_value=True), \
             patch("os.access", return_value=True), \
             patch.dict(os.environ, {"COPILOT_CLI": "/bad/copilot"}):
            with self.assertRaises(SystemExit):
                detect_copilot_bin()


# ---------------------------------------------------------------------------
# build_env_file
# ---------------------------------------------------------------------------


class BuildEnvFileTests(unittest.TestCase):
    def test_writes_shell_mode_argv(self):
        content = build_env_file("/bin/copilot", "gpt-5-mini", 90, "127.0.0.1", 8765)
        self.assertIn("COPILOT_SERVICE_SHELL_MODE=argv", content)

    def test_writes_shell_command(self):
        content = build_env_file("/bin/copilot", "gpt-5-mini", 90, "127.0.0.1", 8765)
        self.assertIn("COPILOT_SERVICE_SHELL_COMMAND=/bin/copilot", content)

    def test_does_not_contain_ask_or_stdin(self):
        content = build_env_file("/bin/copilot", "gpt-5-mini", 90, "127.0.0.1", 8765)
        self.assertNotIn("ask --stdin", content)
        self.assertNotIn("--stdin", content)

    def test_writes_provider_shell(self):
        content = build_env_file("/bin/copilot", "gpt-5-mini", 90, "127.0.0.1", 8765)
        self.assertIn("COPILOT_SERVICE_PROVIDER=shell", content)

    def test_writes_model(self):
        content = build_env_file("/bin/copilot", "gpt-5-turbo", 90, "127.0.0.1", 8765)
        self.assertIn("COPILOT_SERVICE_MODEL=gpt-5-turbo", content)

    def test_writes_no_color(self):
        content = build_env_file("/bin/copilot", "gpt-5-mini", 90, "127.0.0.1", 8765)
        self.assertIn("NO_COLOR=1", content)


# ---------------------------------------------------------------------------
# build_unit_file
# ---------------------------------------------------------------------------


class BuildUnitFileTests(unittest.TestCase):
    def _unit(self):
        return build_unit_file(
            "/srv/copilot-service",
            "/srv/copilot-service/.venv",
            "/home/user/.config/copilot-service/env",
            "127.0.0.1",
            8765,
        )

    def test_has_environment_file(self):
        self.assertIn("EnvironmentFile=/home/user/.config/copilot-service/env", self._unit())

    def test_execstart_uses_venv_binary(self):
        self.assertIn(
            "ExecStart=/srv/copilot-service/.venv/bin/copilot-service serve",
            self._unit(),
        )

    def test_execstart_has_host_and_port(self):
        unit = self._unit()
        self.assertIn("--host 127.0.0.1", unit)
        self.assertIn("--port 8765", unit)

    def test_has_no_new_privileges(self):
        self.assertIn("NoNewPrivileges=true", self._unit())

    def test_has_restart_on_failure(self):
        self.assertIn("Restart=on-failure", self._unit())


# ---------------------------------------------------------------------------
# _run_smoke_test
# ---------------------------------------------------------------------------


class SmokeTestTests(unittest.TestCase):
    def test_passes_on_valid_decision(self):
        good_body = {
            "ok": True,
            "content": {"decision": "test", "confidence": 0.9, "reason": "match"},
            "errors": [],
            "meta": {},
        }
        with patch("copilot_service.service._http_post", return_value=(200, good_body)):
            rc = _run_smoke_test("127.0.0.1", 8765)
        self.assertEqual(rc, 0)

    def test_fails_on_invalid_provider_output(self):
        bad_body = {
            "ok": True,
            "content": {"decision": "fallback", "confidence": 0.0, "reason": "fallback due to invalid provider output"},
            "errors": [{"code": "invalid_provider_output", "message": "no valid JSON found"}],
            "meta": {},
        }
        with patch("copilot_service.service._http_post", return_value=(200, bad_body)):
            rc = _run_smoke_test("127.0.0.1", 8765)
        self.assertNotEqual(rc, 0)

    def test_fails_on_connection_error(self):
        with patch("copilot_service.service._http_post", return_value=(0, {"error": "refused"})):
            rc = _run_smoke_test("127.0.0.1", 8765)
        self.assertNotEqual(rc, 0)

    def test_fails_when_reason_is_fallback_due_to_invalid(self):
        bad_body = {
            "ok": True,
            "content": {
                "decision": "fallback",
                "confidence": 0.0,
                "reason": "fallback due to invalid provider output",
            },
            "errors": [],
            "meta": {},
        }
        with patch("copilot_service.service._http_post", return_value=(200, bad_body)):
            rc = _run_smoke_test("127.0.0.1", 8765)
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# CLI integration: service subparser exists
# ---------------------------------------------------------------------------


class ServiceCliParserTests(unittest.TestCase):
    def test_service_subcommands_parse(self):
        from copilot_service.cli import _build_parser
        parser = _build_parser()

        for subcmd in ["status", "restart", "logs", "test"]:
            args = parser.parse_args(["service", subcmd])
            self.assertEqual(args.command, "service")
            self.assertEqual(args.service_command, subcmd)

    def test_install_flags_parse(self):
        from copilot_service.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "service", "install",
            "--source-dir", "/tmp/repo",
            "--copilot-bin", "/usr/bin/copilot",
            "--model", "gpt-5-mini",
            "--skip-provider-smoke",
        ])
        self.assertEqual(args.source_dir, "/tmp/repo")
        self.assertEqual(args.copilot_bin, "/usr/bin/copilot")
        self.assertEqual(args.model, "gpt-5-mini")
        self.assertTrue(args.skip_provider_smoke)

    def test_uninstall_flags_parse(self):
        from copilot_service.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["service", "uninstall", "--remove-config", "--yes"])
        self.assertTrue(args.remove_config)
        self.assertTrue(args.yes)

    def test_logs_flags_parse(self):
        from copilot_service.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["service", "logs", "-n", "50", "-f"])
        self.assertEqual(args.lines, 50)
        self.assertTrue(args.follow)


if __name__ == "__main__":
    unittest.main()
