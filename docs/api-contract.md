# API Contract

**Service:** copilot-caas / copilot-service  
**Base URL:** `http://127.0.0.1:8765`  
**Default model:** `gpt-5-mini`  
**Transport:** HTTP JSON over localhost  
**Content-Type:** `application/json`

---

## Schemas

### BridgeRequest

```json
{
  "task": "route-topic",
  "model": "gpt-5-mini",
  "input": {},
  "options": {}
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `task` | string | yes | Task name (see Tasks section) |
| `model` | string | no | LLM model identifier; defaults to server `COPILOT_SERVICE_MODEL` |
| `input` | object | no | Task-specific input fields |
| `options` | object | no | Task-specific option flags |

### BridgeResponse

```json
{
  "ok": true,
  "task": "route-topic",
  "provider": "shell",
  "model": "gpt-5-mini",
  "content": {},
  "raw_text": null,
  "errors": [],
  "meta": {
    "duration_ms": 42,
    "attempts": 1
  }
}
```

| Field | Type | Description |
|---|---|---|
| `ok` | bool | `true` if the task succeeded |
| `task` | string | Echo of the requested task name |
| `provider` | string | Provider that handled the request |
| `model` | string | Model used |
| `content` | object | Parsed task-specific result |
| `raw_text` | string\|null | Raw provider output before parsing |
| `errors` | array of BridgeError | Non-empty when `ok=false` or partial failures occurred |
| `meta.duration_ms` | int | Wall-clock time in milliseconds |
| `meta.attempts` | int | Number of provider attempts |

### BridgeError

```json
{
  "code": "invalid_json",
  "message": "Could not extract JSON from provider output."
}
```

| Code | Meaning |
|---|---|
| `unknown_task` | Requested task is not registered |
| `provider_error` | Provider subprocess or HTTP call failed |
| `invalid_provider_output` | Provider returned unparseable output |
| `invalid_request` | Malformed or missing request fields |

---

## Endpoints

### GET /health

Check that copilot-service is running.

**Response 200:**

```json
{
  "ok": true,
  "status": "ok",
  "service": "copilot-service",
  "version": "0.2.0",
  "default_model": "gpt-5-mini"
}
```

Minimum acceptable response: `{"ok": true}` or `{"status": "ok"}`.

---

### POST /v1/ask

Generic task endpoint. Accepts any registered task.

**Request:**

```json
{
  "task": "freeform",
  "model": "gpt-5-mini",
  "input": { "prompt": "Explain this error" },
  "options": {}
}
```

**Response:** BridgeResponse (see schema above).

HTTP status is always `200` for valid requests, even when `ok=false`.
Use the `ok` field and `errors` array to determine outcome.

---

### POST /v1/tasks/route-topic

Shorthand for `POST /v1/ask` with `task=route-topic`.
Accepts either a full BridgeRequest or a bare input object.

---

## Tasks

### route-topic

Routes a message to one of the provided topic keys.

**Input:**

```json
{
  "title": "Article title",
  "message": "Full message text",
  "article_excerpt": "First 500 chars",
  "topics": {
    "asr": "Automatic Speech Recognition",
    "nlp": "Natural Language Processing"
  },
  "fallback_key": "fallback"
}
```

**Content output:**

```json
{
  "decision": "asr",
  "confidence": 0.85,
  "reason": "The article is about speech recognition."
}
```

---

### freeform

Open-ended prompt. Returns raw LLM response.

**Input:**

```json
{
  "prompt": "Explain this error",
  "system": "You are a concise engineering assistant."
}
```

**Content output:**

```json
{
  "text": "The error means ..."
}
```

---

### classify *(planned)*

Classify text into one of N labels.

---

### extract-json *(planned)*

Extract a structured JSON object from unstructured text.

---

### summarize *(planned)*

Summarize a document or text block.

---

## CLI

```bash
# Run a task from a JSON file
copilot-caas ask --input request.json

# Run a task from stdin
cat request.json | copilot-caas ask --stdin

# Run freeform task directly
copilot-caas ask --task freeform --prompt "Explain this error"

# Start REST server
copilot-caas serve --host 127.0.0.1 --port 8765
```

---

## Python client

```python
from copilot_service.client import CopilotServiceClient

client = CopilotServiceClient()                    # connects to http://127.0.0.1:8765

# Check server is up
client.health()

# Freeform prompt
result = client.freeform("Explain this error")
if result.ok:
    print(result.content["text"])

# Route-topic task
result = client.route_topic(
    title="Speech synthesis paper",
    message="...",
    article_excerpt="...",
    topics={"asr": "Speech Recognition", "nlp": "NLP"},
    fallback_key="other",
)
print(result.content["decision"])

# Generic ask
result = client.ask("route-topic", input={...})
```

See [src/copilot_service/client.py](../src/copilot_service/client.py) for full reference.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `COPILOT_SERVICE_PROVIDER` | `shell` | Provider: `shell`, `fake` |
| `COPILOT_SERVICE_SHELL_COMMAND` | *(empty)* | Command for shell provider |
| `COPILOT_SERVICE_MODEL` | `gpt-5-mini` | Default model |
| `COPILOT_SERVICE_TIMEOUT_SECONDS` | `90` | Provider call timeout |
| `COPILOT_SERVICE_HOST` | `127.0.0.1` | Server bind host |
| `COPILOT_SERVICE_PORT` | `8765` | Server bind port |
