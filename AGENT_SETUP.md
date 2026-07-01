# LLM Coding Agent Setup Guide

This document is for an LLM coding agent setting up this repository on a fresh
machine. Follow it in order. Do not skip verification commands.

## Goal

Prepare the local Meeting Minutes ASR app so it can:

- run the FastAPI web UI,
- use bundled Qwen ASR and ForcedAligner models,
- use bundled pyannote speaker diarization without a Hugging Face token,
- generate meeting minutes through the configured OpenAI-compatible LLM API.

## Rules

- Never print or commit `.env`, API keys, Hugging Face tokens, or `zai_api.md`.
- Prefer the bundled local model paths in `.env`.
- If a command fails, keep the exact stderr and diagnose from that output.
- After changing `.env` or installing dependencies, restart the app server.

## 1. Verify Base Tools

Run:

```bash
git lfs version
uv --version
ffmpeg -version
```

Expected:

- `git-lfs` is installed.
- `uv` is installed.
- `ffmpeg` prints version information.

On macOS, install missing tools with:

```bash
brew install git-lfs ffmpeg uv
```

## 2. Pull Model Files

Run:

```bash
git lfs install
git lfs pull
```

Then confirm model files are real binaries, not tiny Git LFS pointer files:

```bash
find models -maxdepth 3 -type f -print -exec sh -c 'printf "%s " "$1"; wc -c < "$1"' sh {} \;
```

Expected examples:

- `models/Qwen3-ASR-0.6B-4bit/model.safetensors` is large.
- `models/Qwen3-ForcedAligner-0.6B-8bit/model.safetensors` is large.
- `models/pyannote-speaker-diarization-community-1/embedding/pytorch_model.bin` is large.

If model files are only a few hundred bytes, run `git lfs pull` again.

## 3. Install Dependencies

For the full local app with speaker diarization:

```bash
uv sync --extra diarization
```

Verify pyannote is installed:

```bash
uv run python -c "import pyannote.audio; print('pyannote.audio OK')"
```

If this fails with `ModuleNotFoundError`, rerun:

```bash
uv sync --extra diarization
```

## 4. Create `.env`

Run:

```bash
cp .env.example .env
```

Use local bundled model paths:

```env
APP_ENV=development

ASR_ENGINE=qwen3_asr_mlx
ASR_MODEL=models/Qwen3-ASR-0.6B-4bit
ASR_LANGUAGE=ko

ALIGNMENT_ENGINE=qwen3_forced_mlx
ALIGNMENT_MODEL=models/Qwen3-ForcedAligner-0.6B-8bit

DIARIZATION_ENGINE=pyannote
DIARIZATION_MODEL=models/pyannote-speaker-diarization-community-1
DIARIZATION_HF_TOKEN=
DIARIZATION_DEVICE=auto
```

Configure one LLM provider.

For z.ai development:

```env
LLM_PROVIDER=zai
LLM_BASE_URL=https://api.z.ai/api/paas/v4
LLM_API_KEY=<z-ai-api-key>
LLM_MODEL=<model-name>
```

For an internal OpenAI-compatible endpoint:

```env
LLM_PROVIDER=internal
LLM_BASE_URL=<internal-openai-compatible-base-url>
LLM_API_KEY=<internal-api-key>
LLM_MODEL=<model-name>
```

Do not use `LLM_PROVIDER=fake` unless `APP_ENV=testing`.

## 5. Verify Diarization Directly

Run this before testing the web app:

```bash
uv run python -m app.workers.pyannote_diarization_worker \
  --audio simple_test/chunks/test_010.wav \
  --model models/pyannote-speaker-diarization-community-1
```

Expected:

- exit code `0`,
- JSON array output,
- entries with `SPEAKER_00` or `SPEAKER_01`.

`DIARIZATION_DEVICE=auto` uses CUDA when available, then Apple Silicon MPS, and
falls back to CPU. If accelerator execution fails in a specific environment, set
`DIARIZATION_DEVICE=cpu`, restart the app, and rerun the direct worker test.

Common failures:

- `pyannote.audio is not installed.`
  Fix: `uv sync --extra diarization`.
- `PYANNOTE_AUTH_TOKEN is required`
  Cause: the command is using a remote Hugging Face model id instead of local
  `models/...`, or direct worker invocation has no token.
  Fix: use `DIARIZATION_MODEL=models/pyannote-speaker-diarization-community-1`.
- model loading error with tiny files
  Cause: Git LFS files were not pulled.
  Fix: `git lfs pull`.

## 6. Verify ASR Directly

Run:

```bash
APP_ENV=development \
ASR_ENGINE=qwen3_asr_mlx \
ASR_MODEL=models/Qwen3-ASR-0.6B-4bit \
ASR_LANGUAGE=ko \
LLM_PROVIDER=zai \
LLM_API_KEY=dummy \
LLM_MODEL=dummy \
uv run scripts/test_asr.py simple_test/chunks/test_010.wav
```

Expected:

- JSON-like output with `model`, `language`, `text`, and `segments`.

On non-Apple Silicon machines, MLX ASR may not run. Record that limitation
instead of changing production settings to fake adapters.

## 7. Run Quality Checks

Run:

```bash
uv run ruff check .
uv run basedpyright
PYTHONDONTWRITEBYTECODE=1 uv run pytest -q -p no:cacheprovider
```

Expected:

- ruff passes,
- basedpyright reports `0 errors`,
- pytest passes.

## 8. Start The App

Run:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

After any dependency install or `.env` change, stop and restart this server.

## 9. API Smoke Flow

Upload:

```bash
curl -F "file=@simple_test/chunks/test_010.wav" http://127.0.0.1:8000/uploads
```

Create a conversion job with speaker separation enabled:

```bash
curl -H "content-type: application/json" \
  -d '{"upload_id":"<upload-id>","speaker_separation_enabled":true}' \
  http://127.0.0.1:8000/conversion-jobs
```

Poll:

```bash
curl http://127.0.0.1:8000/conversion-jobs/<job-id>
```

Expected when completed:

- `status` is `completed`,
- `transcript.text` contains `[SPEAKER_00]` or `[SPEAKER_01]`,
- `transcript.speaker_transcript` contains speaker labels,
- `transcript.speaker_segments` is not empty.

## 10. Failure Triage

If the UI says speaker diarization failed, run:

```bash
uv run python -m app.workers.pyannote_diarization_worker \
  --audio simple_test/chunks/test_010.wav \
  --model models/pyannote-speaker-diarization-community-1
```

Use the direct worker stderr as the source of truth.

If the direct worker succeeds but the app fails:

1. Check `.env` uses the same local diarization model path.
2. Restart the server.
3. Confirm the server is running from this repository and this virtual env.
4. Re-run the conversion job.

If the direct worker fails:

1. Fix the exact stderr first.
2. Re-run the worker until it exits `0`.
3. Only then test the web app.
