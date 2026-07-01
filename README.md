# Meeting Minutes ASR

Local FastAPI app for uploading meeting recordings, transcribing them with a
local ASR worker, and generating Markdown/JSON meeting minutes through an
OpenAI-compatible LLM API.

## Setup

If you are asking an LLM coding agent to set up this repository, first point it
to [`AGENT_SETUP.md`](AGENT_SETUP.md). That document is written as an
agent-executable checklist with exact commands, expected outputs, and common
failure diagnoses.

```bash
git lfs install
git lfs pull
uv sync
cp .env.example .env
```

Install `ffmpeg` and use an Apple Silicon Mac for the MLX ASR path. The Qwen3
ASR, Qwen3 ForcedAligner, and pyannote community diarization snapshots are
vendored under `models/` and tracked with Git LFS, so a normal user does not
need a Hugging Face token for the default local model setup. If `git lfs pull`
is skipped, the files under `models/` remain small pointer files and the local
workers cannot load them.

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
DIARIZATION_ENGINE=fake
LLM_PROVIDER=fake
```

Fake adapters are rejected outside `APP_ENV=testing` so development and
production settings do not accidentally bypass the real ASR/LLM paths.

If you want speaker separation enabled for local development, install the
optional diarization dependencies once:

```bash
uv sync --extra diarization
```

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
`models/Qwen3-ASR-0.6B-4bit`. When speaker diarization is enabled, the app
also runs Qwen3 ForcedAligner to replace coarse ASR timing with word or short
phrase timestamps before speaker labels are applied.

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
ASR_MODEL=models/Qwen3-ASR-0.6B-4bit
ASR_LANGUAGE=ko
ALIGNMENT_ENGINE=qwen3_forced_mlx
ALIGNMENT_MODEL=models/Qwen3-ForcedAligner-0.6B-8bit
```

`ASR_MODEL` can be changed to another MLX-compatible Hugging Face ASR model,
but the worker expects the `mlx_audio.stt.generate` CLI to support it. The
default model is already included in this repository under `models/`. If you
change it back to a Hugging Face model id, the first run downloads and caches it
under `~/.cache/huggingface/hub/`.

Run a model-only smoke test with an existing audio file:

```bash
APP_ENV=development \
ASR_ENGINE=qwen3_asr_mlx \
ASR_MODEL=models/Qwen3-ASR-0.6B-4bit \
ASR_LANGUAGE=ko \
LLM_PROVIDER=zai \
LLM_API_KEY=dummy \
LLM_MODEL=dummy \
uv run scripts/test_asr.py sample.wav
```

Expected output shape:

```json
{
  "model": "models/Qwen3-ASR-0.6B-4bit",
  "language": "ko",
  "text": "...",
  "segments": ["..."]
}
```

For a full API run, start the server with the same `.env` values and call the
upload/transcript endpoints. Uploaded audio is always normalized to 16 kHz mono
WAV with `ffmpeg` before the worker starts.

### Word/Phrase Alignment

`ALIGNMENT_ENGINE=qwen3_forced_mlx` keeps Qwen3-ASR as the transcript source and
uses `models/Qwen3-ForcedAligner-0.6B-8bit` only to create finer
timestamps for the recognized text. This is the recommended mode for meeting
audio because pyannote speaker turns can then be reconciled against short text
spans instead of one long ASR segment.

The aligner runs only when diarization returns speaker turns. If the aligner is
disabled, the app still has a deterministic coarse fallback that splits a long
ASR segment across overlapping speaker turns, but ForcedAligner produces better
speaker boundaries for real meetings.

Common checks:

- `ModuleNotFoundError: mlx_audio`: run `uv sync` and confirm `mlx-audio` is in
  the active environment.
- `ffmpeg` errors: install `ffmpeg` and confirm `ffmpeg -version` works.
- First run is slow: the Hugging Face model is being downloaded and cached.
- Non-Apple Silicon machines: use `ASR_ENGINE=fake` only with
  `APP_ENV=testing`, or replace the worker with a compatible ASR backend.

## Speaker Diarization

Speaker separation is implemented as an optional post-ASR step. The selected
default backend is `pyannote/speaker-diarization-community-1` because it is a
local open-source diarization pipeline, improves on pyannote 3.1, and publishes
meeting-style multilingual benchmark results including AISHELL-4 and
AliMeeting. The app aligns pyannote speaker turns with Qwen3 ForcedAligner
timestamps and stores both `speaker_segments` and `speaker_transcript`.

Configure real diarization with the bundled local model:

```env
DIARIZATION_ENGINE=pyannote
DIARIZATION_MODEL=models/pyannote-speaker-diarization-community-1
DIARIZATION_HF_TOKEN=
DIARIZATION_DEVICE=auto
```

The model files are committed to this repository with Git LFS. With the local
`models/...` path above, `DIARIZATION_HF_TOKEN` is not required. Install
`pyannote.audio` in a Python version supported by pyannote:

```bash
uv sync --extra diarization
```

`DIARIZATION_DEVICE=auto` uses CUDA when available, then Apple Silicon MPS, and
falls back to CPU. On an Apple Silicon Mac this is much faster than CPU-only
diarization. Set `DIARIZATION_DEVICE=cpu` only when accelerator execution causes
environment-specific PyTorch issues.

If you replace `DIARIZATION_MODEL` with a remote Hugging Face id such as
`pyannote/speaker-diarization-community-1`, then you must accept the model terms
on Hugging Face and provide `DIARIZATION_HF_TOKEN`. The token is passed to the
worker through `PYANNOTE_AUTH_TOKEN` and is not sent as a command-line argument.
If a remote model is configured without a token, `/transcripts` returns
`503 Diarization is not configured`.

For CI or local contract tests only:

```env
APP_ENV=testing
DIARIZATION_ENGINE=fake
```

Fake diarization alternates deterministic `SPEAKER_00` and `SPEAKER_01` labels
and is rejected outside `APP_ENV=testing`.

Current local verification note: real Qwen3-ASR, Qwen3 ForcedAligner, and
`pyannote/speaker-diarization-community-1` were verified through the HTTP API
against a five-minute `simple_test` audio chunk.

### About `pyannote/speaker-diarization-3.1`

The app can be pointed at remote 3.1 by changing the model value and adding a
Hugging Face token:

```env
DIARIZATION_ENGINE=pyannote
DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
DIARIZATION_HF_TOKEN=<hugging-face-token>
```

`speaker-diarization-3.1` is still usable, but it is a legacy pyannote pipeline.
It requires accepting both `pyannote/speaker-diarization-3.1` and the internal
`pyannote/segmentation-3.0` model conditions on Hugging Face. In this local
review, the supplied token could download the 3.1 pipeline config, but
`pyannote/segmentation-3.0` returned HTTP 403, so a full 3.1 run is blocked
until that second model access is accepted for the token.

For Korean meeting-style audio, `speaker-diarization-community-1` remains the
recommended default because its official benchmark table reports better DER
than 3.1 on AISHELL-4 and AliMeeting and it provides exclusive diarization for
cleaner transcript timestamp reconciliation.

## Scope

A browser UI is served from `/` by the FastAPI app. It supports audio upload,
transcription, speaker-labeled source display when configured, minutes
generation, result lookup, and Markdown download. docx/PDF export, login, and
template management UI remain out of scope.
