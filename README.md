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

### Qwen3-ASR Model Setup

The Qwen3-ASR path is designed for Apple Silicon through MLX. It does not use
the z.ai API key; the ASR model is downloaded from Hugging Face on first run.

Prerequisites:

```bash
brew install ffmpeg
uv sync
```

Configure `.env`:

```env
APP_ENV=development
ASR_ENGINE=qwen3_asr_mlx
ASR_MODEL=mlx-community/Qwen3-ASR-0.6B-4bit
ASR_LANGUAGE=ko
```

`ASR_MODEL` can be changed to another MLX-compatible Hugging Face ASR model,
but the worker expects the `mlx_audio.stt.generate` CLI to support it. The
default model is public and is cached under the local Hugging Face cache,
typically `~/.cache/huggingface/hub/`.

Run a model-only smoke test with an existing audio file:

```bash
APP_ENV=development \
ASR_ENGINE=qwen3_asr_mlx \
ASR_MODEL=mlx-community/Qwen3-ASR-0.6B-4bit \
ASR_LANGUAGE=ko \
LLM_PROVIDER=zai \
LLM_API_KEY=dummy \
LLM_MODEL=dummy \
uv run scripts/test_asr.py sample.wav
```

Expected output shape:

```json
{
  "model": "mlx-community/Qwen3-ASR-0.6B-4bit",
  "language": "ko",
  "text": "...",
  "segments": ["..."]
}
```

For a full API run, start the server with the same `.env` values and call the
upload/transcript endpoints. Uploaded audio is always normalized to 16 kHz mono
WAV with `ffmpeg` before the worker starts.

Common checks:

- `ModuleNotFoundError: mlx_audio`: run `uv sync` and confirm `mlx-audio` is in
  the active environment.
- `ffmpeg` errors: install `ffmpeg` and confirm `ffmpeg -version` works.
- First run is slow: the Hugging Face model is being downloaded and cached.
- Non-Apple Silicon machines: use `ASR_ENGINE=fake` only with
  `APP_ENV=testing`, or replace the worker with a compatible ASR backend.

## Scope

No UI is shipped in this first version. Speaker diarization, word-level
timestamps, docx/PDF export, login, and template management UI remain out of
scope.
