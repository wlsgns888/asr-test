const form = document.querySelector("#minutes-form");
const fileInput = document.querySelector("#audio-file");
const templateInput = document.querySelector("#template");
const runButton = document.querySelector("#run-button");
const runState = document.querySelector("#run-state");
const resultOutput = document.querySelector("#result-output");
const resultMeta = document.querySelector("#result-meta");
const sourceOutput = document.querySelector("#source-output");
const sourceMeta = document.querySelector("#source-meta");
const minutesMeta = document.querySelector("#minutes-meta");
const copyButton = document.querySelector("#copy-button");
const downloadButton = document.querySelector("#download-button");
const speakerStatus = document.querySelector("#speaker-status");
const speakerNote = document.querySelector("#speaker-note");
const steps = [...document.querySelectorAll(".step")];

const stepOrder = ["upload", "transcript", "minutes", "result"];
let currentMarkdown = "";
let currentMinutesId = "";

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
  sourceOutput.textContent = "";
  sourceMeta.textContent = "대기";
  minutesMeta.textContent = "실패";
  copyButton.disabled = true;
  downloadButton.disabled = true;
  currentMarkdown = "";
  currentMinutesId = "";
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
    speakerStatus.textContent = speaker.available ? "지원" : "설정 필요";
    speakerNote.textContent = speaker.available
      ? `${speaker.engine} 엔진으로 발화자 구분을 사용할 수 있습니다.`
      : "발화자 구분 코드는 적용되어 있으며, pyannote 모델 사용을 위해 Hugging Face 토큰과 모델 조건 수락이 필요합니다.";
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
  sourceMeta.textContent = transcript.speaker_transcript
    ? `${transcript.language || "원본"} · 화자 구분`
    : transcript.language || "원본";
  sourceOutput.textContent =
    transcript.speaker_transcript || transcript.text || "(전사 원본 없음)";
  minutesMeta.textContent = "Markdown";
  resultOutput.textContent = result.markdown;
  currentMarkdown = result.markdown;
  currentMinutesId = result.minutes_id;
  copyButton.disabled = false;
  downloadButton.disabled = false;
}

function downloadMarkdown() {
  if (!currentMarkdown) {
    return;
  }

  const fileName = currentMinutesId
    ? `meeting-minutes-${currentMinutesId}.md`
    : "meeting-minutes.md";
  const blob = new Blob([currentMarkdown], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    showError("음성 파일을 선택해 주세요.");
    return;
  }

  resultOutput.textContent = "";
  sourceOutput.textContent = "";
  sourceMeta.textContent = "대기";
  minutesMeta.textContent = "대기";
  copyButton.disabled = true;
  downloadButton.disabled = true;
  currentMarkdown = "";
  currentMinutesId = "";
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

downloadButton.addEventListener("click", downloadMarkdown);

loadCapabilities();
