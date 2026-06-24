# Meeting Minutes ASR

Local FastAPI app for uploading meeting recordings, transcribing them with a
local ASR worker, and generating Markdown/JSON meeting minutes through an
OpenAI-compatible LLM API.

## Setup

```bash
uv sync
cp .env.example .env
```

Install `ffmpeg` and use an Apple Silicon Mac for the MLX ASR path.

Fill `.env` with the target provider values. Development can use z.ai:

```env
LLM_PROVIDER=zai
LLM_BASE_URL=https://api.z.ai/api/paas/v4
LLM_API_KEY=${ZAI_API_KEY}
LLM_MODEL=<model-name>
```

Internal deployment can switch the same service code to a company endpoint:

```env
LLM_PROVIDER=internal
LLM_BASE_URL=https://internal-llm.company.local/v1
LLM_API_KEY=${INTERNAL_LLM_API_KEY}
LLM_MODEL=internal-model-name
```

For local smoke tests without external AI calls:

```env
APP_ENV=testing
ASR_ENGINE=fake
LLM_PROVIDER=fake
```

Fake adapters are rejected outside `APP_ENV=testing` so development and
production settings do not accidentally bypass the real ASR/LLM paths.

## Run

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## API Flow

Upload audio:

```bash
curl -F "file=@sample.wav" http://127.0.0.1:8000/uploads
```

Create transcript:

```bash
curl -H "content-type: application/json" \
  -d '{"upload_id":"<upload-id>"}' \
  http://127.0.0.1:8000/transcripts
```

Create minutes:

```bash
curl -H "content-type: application/json" \
  -d '{"transcript_id":"<transcript-id>"}' \
  http://127.0.0.1:8000/minutes
```

Fetch saved result:

```bash
curl http://127.0.0.1:8000/results/<minutes-id>
```

## Checks

```bash
uv run pytest
uv run basedpyright
uv run ruff check .
uv run ruff format --check .
```

Run the live API smoke test:

```bash
bash scripts/qa_http.sh
```

## ASR Worker

The default engine launches `app.workers.qwen3_asr_worker` in a subprocess so
the FastAPI process does not retain the ASR model after each job. Install
`mlx-audio` in the target Mac environment before running the Qwen3-ASR engine.
The worker calls `mlx_audio.stt.generate` with
`mlx-community/Qwen3-ASR-0.6B-4bit`.

## Scope

No UI is shipped in this first version. Speaker diarization, word-level
timestamps, docx/PDF export, login, and template management UI remain out of
scope.
