#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="$ROOT/.omo/evidence"
TMP_DIR="$(mktemp -d)"
PORT="${PORT:-8765}"
BASE_URL="http://127.0.0.1:${PORT}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
mkdir -p "$EVIDENCE_DIR"

cleanup() {
  local code=$?
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID"
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
  local port_state
  port_state="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN || true)"
  printf "cleanup: killed pid=%s; removed tmp=%s; port %s clear=%s\n" "${SERVER_PID:-none}" "$TMP_DIR" "$PORT" "${port_state:-yes}"
  exit "$code"
}
trap cleanup EXIT

cd "$ROOT"
APP_ENV=testing \
ASR_ENGINE=fake \
LLM_PROVIDER=fake \
LLM_API_KEY=test-key \
LLM_MODEL=fake-minutes \
DATA_DIR="$TMP_DIR/data" \
UPLOAD_DIR="$TMP_DIR/data/uploads" \
WAV_DIR="$TMP_DIR/data/wav" \
TRANSCRIPT_DIR="$TMP_DIR/data/transcripts" \
MINUTES_DIR="$TMP_DIR/data/minutes" \
uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$TMP_DIR/server.log" 2>&1 &
SERVER_PID=$!

for _ in {1..50}; do
  if curl -fsS "$BASE_URL/docs" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i anullsrc=r=16000:cl=mono -t 0.1 \
  "$TMP_DIR/sample.wav"
curl -i -F "file=@$TMP_DIR/sample.wav;type=audio/wav" "$BASE_URL/uploads" | tee "$EVIDENCE_DIR/qa-upload.txt"
UPLOAD_ID="$("$PYTHON_BIN" - "$EVIDENCE_DIR/qa-upload.txt" <<'PY'
from pathlib import Path
import json
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
print(json.loads(text[text.index("{") :])["upload_id"])
PY
)"

curl -i -H "content-type: application/json" -d "{\"upload_id\":\"$UPLOAD_ID\"}" "$BASE_URL/transcripts" | tee "$EVIDENCE_DIR/qa-transcript.txt"
TRANSCRIPT_ID="$("$PYTHON_BIN" - "$EVIDENCE_DIR/qa-transcript.txt" <<'PY'
from pathlib import Path
import json
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
print(json.loads(text[text.index("{") :])["transcript_id"])
PY
)"

curl -i -H "content-type: application/json" -d "{\"transcript_id\":\"$TRANSCRIPT_ID\"}" "$BASE_URL/minutes" | tee "$EVIDENCE_DIR/qa-minutes.txt"
MINUTES_ID="$("$PYTHON_BIN" - "$EVIDENCE_DIR/qa-minutes.txt" <<'PY'
from pathlib import Path
import json
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
print(json.loads(text[text.index("{") :])["minutes_id"])
PY
)"

curl -i "$BASE_URL/results/$MINUTES_ID" | tee "$EVIDENCE_DIR/qa-result.txt"
curl -i -F "file=@$ROOT/requiremens.md;type=text/plain" "$BASE_URL/uploads" | tee "$EVIDENCE_DIR/qa-reject.txt"
