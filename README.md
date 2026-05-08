# copilot-service

![copilot-as-a-service](assets/caas.png)

`copilot-service` provides a stable local CLI and REST wrapper around Copilot/LLM CLI tooling so scripts and agents can call a normalized task API.

## What problem this solves

Different LLM CLIs have different prompt formats and output styles. This project gives one stable contract for task-based calls (`route-topic`, `freeform`) and isolates provider setup in local config.

## Releases

Automated releases are available through GitHub Actions.
See [docs/release.md](docs/release.md) for full instructions.

## CLI UX

Running `copilot-caas` with no arguments shows a colorful welcome screen and exits 0:

```
copilot-caas
```

Check the installed version:

```
copilot-caas --version
```

Run a task:

```
copilot-caas ask --input examples/route-topic-request.json
```

Colors are automatically disabled when `NO_COLOR` is set or output is not a TTY.

## Quickstart (fake provider)

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .

export COPILOT_SERVICE_PROVIDER=fake
export COPILOT_SERVICE_FAKE_RESPONSE='{"decision":"asr","confidence":0.8,"reason":"fake"}'
copilot-service ask --input examples/route-topic-request.json
```

## Quickstart (shell provider)

```bash
export COPILOT_SERVICE_PROVIDER=shell
export COPILOT_SERVICE_SHELL_COMMAND='python -c "import sys; print(sys.stdin.read())"'
copilot-service ask --task freeform --prompt "Explain this"
```

## REST usage

```bash
copilot-service serve --host 127.0.0.1 --port 8765

curl -sS http://127.0.0.1:8765/health
curl -sS http://127.0.0.1:8765/v1/ask \
  -H 'content-type: application/json' \
  --data @examples/freeform-request.json
curl -sS http://127.0.0.1:8765/v1/tasks/route-topic \
  -H 'content-type: application/json' \
  --data @examples/route-topic-request.json
```

## Article-ingestion integration example

See `examples/article-ingestion-usage.sh` for a simple pipeline wrapper around the `route-topic` task.

## Environment

- `COPILOT_SERVICE_PROVIDER` (`shell` for MVP, `fake` for tests)
- `COPILOT_SERVICE_SHELL_COMMAND` (provider command)
- `COPILOT_SERVICE_MODEL` (default `gpt-5-mini`)
- `COPILOT_SERVICE_TIMEOUT_SECONDS` (default `90`)
- `COPILOT_SERVICE_HOST` (default `127.0.0.1`)
- `COPILOT_SERVICE_PORT` (default `8765`)

## Limitations

- MVP ships only with shell/fake providers.
- Output quality depends on your configured local command and prompt discipline.
- `route-topic` fallback behavior can mask model errors when enabled (default true).

## Security note

REST binds to `127.0.0.1` by default. The shell command is loaded only from local environment/config (never from request payload).
