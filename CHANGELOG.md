# Changelog

All notable changes to this project will be documented in this file.

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
