const form = document.querySelector("#minutes-form");
const fileInput = document.querySelector("#audio-file");
const templateInput = document.querySelector("#template");
const runButton = document.querySelector("#run-button");
const runState = document.querySelector("#run-state");
const resultOutput = document.querySelector("#result-output");
const resultMeta = document.querySelector("#result-meta");
const copyButton = document.querySelector("#copy-button");
const speakerStatus = document.querySelector("#speaker-status");
const speakerNote = document.querySelector("#speaker-note");
const steps = [...document.querySelectorAll(".step")];

const stepOrder = ["upload", "transcript", "minutes", "result"];

function setStep(current, complete = []) {
  steps.forEach((step) => {
    const key = step.dataset.step;
    step.classList.toggle("is-active", key === current);
    step.classList.toggle("is-complete", complete.includes(key));
  });
}

function setBusy(isBusy, label) {
  runButton.disabled = isBusy;
  runState.textContent = label;
}

function showError(message) {
  resultMeta.textContent = "오류가 발생했습니다.";
  resultOutput.textContent = message;
  copyButton.disabled = true;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof body === "object" && body.detail ? body.detail : body;
    throw new Error(`${response.status} ${detail || response.statusText}`);
  }

  return body;
}

async function loadCapabilities() {
  try {
    const data = await requestJson("/capabilities");
    const speaker = data.speaker_separation;
    speakerStatus.textContent = speaker.available ? "지원" : "현재 미지원";
    speakerNote.textContent = speaker.available
      ? "발화자 구분을 사용할 수 있습니다."
      : "현재 Qwen3-ASR MLX 워커는 화자 라벨이나 화자별 시간 정렬을 반환하지 않습니다. 별도 diarization 백엔드와 전사 정렬을 추가하면 기술적으로 구현 가능합니다.";
    speakerNote.classList.toggle("is-warning", !speaker.available);
  } catch (error) {
    speakerStatus.textContent = "확인 실패";
    speakerNote.textContent = error.message;
    speakerNote.classList.add("is-error");
  }
}

async function uploadAudio(file) {
  const payload = new FormData();
  payload.append("file", file);
  return requestJson("/uploads", {
    method: "POST",
    body: payload,
  });
}

async function createTranscript(uploadId) {
  return requestJson("/transcripts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId }),
  });
}

async function createMinutes(transcriptId, template) {
  return requestJson("/minutes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript_id: transcriptId,
      template,
    }),
  });
}

async function fetchResult(minutesId) {
  return requestJson(`/results/${minutesId}`);
}

function renderResult(result, transcript) {
  resultMeta.textContent = `회의록 ID ${result.minutes_id} · 전사 ID ${transcript.transcript_id}`;
  resultOutput.textContent = result.markdown;
  copyButton.disabled = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    showError("음성 파일을 선택해 주세요.");
    return;
  }

  resultOutput.textContent = "";
  copyButton.disabled = true;
  setBusy(true, "업로드 중");
  setStep("upload");

  try {
    const upload = await uploadAudio(file);
    setBusy(true, "전사 중");
    setStep("transcript", ["upload"]);

    const transcript = await createTranscript(upload.upload_id);
    setBusy(true, "회의록 생성 중");
    setStep("minutes", ["upload", "transcript"]);

    const minutes = await createMinutes(transcript.transcript_id, templateInput.value);
    setBusy(true, "결과 저장 중");
    setStep("result", ["upload", "transcript", "minutes"]);

    const result = await fetchResult(minutes.minutes_id);
    renderResult(result, transcript);
    setStep(null, stepOrder);
    setBusy(false, "완료");
  } catch (error) {
    showError(error.message);
    setBusy(false, "실패");
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultOutput.textContent);
  resultMeta.textContent = "회의록 내용을 클립보드에 복사했습니다.";
});

loadCapabilities();
