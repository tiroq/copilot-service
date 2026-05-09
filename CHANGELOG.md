# Changelog

## 1.1.0 - 2026-05-09

- Maintenance release.

## 1.0.0 - 2026-05-09

- Maintenance release.

## 0.3.0 - 2026-05-08

- Maintenance release.

## Unreleased

- Added documented API contract (`docs/api-contract.md`).
- Added Python client library (`copilot_service.client.CopilotServiceClient`).
- Enriched `/health` endpoint with `status`, `service`, `version`, and `default_model` fields.

## 0.2.0 - 2026-05-08

- Maintenance release.

All notable changes to this project will be documented in this file.

## 0.1.2 - 2026-05-08

- Fixed v0.1.2 release tag mismatch (pyproject.toml version was not bumped before tagging).
- Added automated release workflow (`release.yml`) with version auto-increment.
- Added `docs/release.md` release guide.
- Colorful no-argument welcome screen (`copilot-caas` with no args exits 0).
- Added `--version` flag and `copilot-caas` / `copilot-bridge` CLI entrypoints.
- Fixed PyPI wheel build (missing `[tool.hatch.build.targets.wheel]` config).
- Added `LICENSE` (MIT).

## 0.1.1 - 2026-05-08

- Improved no-argument CLI behavior: running `copilot-caas` without arguments now shows a
  colorful welcome screen and exits with code 0 instead of printing an argparse error.
- Added colorful terminal welcome screen using ANSI escape codes (no external dependencies).
- Added `--version` flag: `copilot-caas --version` prints the installed version.
- Respected `NO_COLOR` environment variable and non-TTY streams to disable colors.
- Preserved clean JSON output for `ask` command; machine-readable responses are unaffected.
- Added `copilot-caas` and `copilot-bridge` CLI entrypoints alongside `copilot-service`.
- Added `LICENSE` file (MIT).
- Fixed PyPI wheel build by adding explicit `[tool.hatch.build.targets.wheel]` configuration.

## 0.1.0 - 2026-05-07

- Initial release.
