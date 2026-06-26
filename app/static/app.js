const form = document.querySelector("#minutes-form");
const fileInput = document.querySelector("#audio-file");
const speakerToggle = document.querySelector("#speaker-separation-enabled");
const summaryPromptInput = document.querySelector("#summary-prompt");
const templateInput = document.querySelector("#template");
const runButton = document.querySelector("#run-button");
const runState = document.querySelector("#run-state");
const resultOutput = document.querySelector("#result-output");
const resultMeta = document.querySelector("#result-meta");
const timingBreakdown = document.querySelector("#timing-breakdown");
const sourceOutput = document.querySelector("#source-output");
const sourceMeta = document.querySelector("#source-meta");
const minutesMeta = document.querySelector("#minutes-meta");
const copyButton = document.querySelector("#copy-button");
const downloadButton = document.querySelector("#download-button");
const speakerStatus = document.querySelector("#speaker-status");
const speakerNote = document.querySelector("#speaker-note");
const steps = [...document.querySelectorAll(".step")];
const progressTitle = document.querySelector("#progress-title");
const progressDetail = document.querySelector("#progress-detail");
const progressBar = document.querySelector("#progress-bar");
const progressLog = document.querySelector("#progress-log");
const progress = window.createProgressView({
  bar: progressBar,
  detail: progressDetail,
  log: progressLog,
  timings: timingBreakdown,
  title: progressTitle,
});

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
  progress.stop();
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
    speakerStatus.classList.toggle("is-ok", speaker.available);
    speakerStatus.classList.toggle("is-warning", !speaker.available);
    speakerNote.textContent = speaker.available
      ? `${speaker.engine} 엔진으로 발화자 구분을 사용할 수 있습니다.`
      : "발화자 구분 코드는 적용되어 있으며, pyannote 모델 사용을 위해 Hugging Face 토큰과 모델 조건 수락이 필요합니다.";
    speakerNote.classList.toggle("is-warning", !speaker.available);
  } catch (error) {
    speakerStatus.textContent = "확인 실패";
    speakerStatus.classList.remove("is-ok");
    speakerStatus.classList.add("is-warning");
    speakerNote.textContent = error.message;
    speakerNote.classList.add("is-error");
  }
}

async function uploadAudio(file) {
  return new Promise((resolve, reject) => {
    const payload = new FormData();
    payload.append("file", file);
    const request = new XMLHttpRequest();
    request.open("POST", "/uploads");
    request.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) {
        progress.set("업로드 중", "브라우저가 파일을 서버로 전송하고 있습니다.");
        return;
      }
      const percent = Math.min(99, Math.round((event.loaded / event.total) * 100));
      progress.set("업로드 중", `${percent}% 전송 완료`, percent);
    });
    request.addEventListener("load", () => {
      const body = window.parseJsonResponse(request.responseText);
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`${request.status} ${body.detail || request.statusText}`));
        return;
      }
      progress.set("업로드 완료", "서버 저장이 끝났습니다.", 100);
      resolve(body);
    });
    request.addEventListener("error", () => {
      reject(new Error("업로드 네트워크 오류"));
    });
    request.send(payload);
  });
}

async function startConversionJob(uploadId, speakerSeparationEnabled) {
  return requestJson("/conversion-jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      window.createConversionJobPayload(uploadId, speakerSeparationEnabled),
    ),
  });
}

async function waitForConversion(jobId) {
  let status = await requestJson(`/conversion-jobs/${jobId}`);
  while (status.status === "queued" || status.status === "running") {
    progress.setFromJob(status);
    await delay(1200);
    status = await requestJson(`/conversion-jobs/${jobId}`);
  }
  progress.setFromJob(status);
  if (status.status === "failed") {
    throw new Error(status.error || status.message || "음성 변환 실패");
  }
  return status;
}

function delay(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

async function createMinutes(transcriptId, template, summaryPrompt) {
  return requestJson("/minutes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      window.createMinutesPayload(transcriptId, template, summaryPrompt),
    ),
  });
}

async function fetchResult(minutesId) {
  return requestJson(`/results/${minutesId}`);
}

function renderResult(result, transcript, timings) {
  resultMeta.textContent = `회의록 ID ${result.minutes_id} · 변환 ID ${transcript.transcript_id}`;
  sourceMeta.textContent = transcript.speaker_transcript
    ? `${transcript.language || "원본"} · 화자 구분`
    : transcript.language || "원본";
  sourceOutput.textContent =
    transcript.speaker_transcript || transcript.text || "(변환 원본 없음)";
  minutesMeta.textContent = "Markdown";
  resultOutput.textContent = result.markdown;
  currentMarkdown = result.markdown;
  currentMinutesId = result.minutes_id;
  copyButton.disabled = false;
  downloadButton.disabled = false;
  progress.renderTimings(timings);
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
  progress.reset();
  setBusy(true, "업로드 중");
  setStep("upload");

  try {
    progress.addLog("업로드 시작");
    const upload = await uploadAudio(file);
    progress.addLog("업로드 완료");
    setBusy(true, "변환 중");
    setStep("transcript", ["upload"]);
    progress.startTimed("음성 변환 중", "50분 음성은 보통 15-30분 이상 걸릴 수 있습니다.");

    const job = await startConversionJob(upload.upload_id, speakerToggle.checked);
    progress.addLog("서버 변환 작업 시작");
    const conversion = await waitForConversion(job.job_id);
    const transcript = conversion.transcript;
    progress.addLog("음성 변환과 화자 정렬 완료");
    setBusy(true, "회의록 생성 중");
    setStep("minutes", ["upload", "transcript"]);
    progress.startTimed("회의록 생성 중", "변환된 내용을 Markdown 회의록으로 정리합니다.");

    const minutes = await createMinutes(
      transcript.transcript_id,
      templateInput.value,
      summaryPromptInput.value,
    );
    progress.addLog("회의록 생성 완료");
    setBusy(true, "결과 저장 중");
    setStep("result", ["upload", "transcript", "minutes"]);
    progress.startTimed("결과 불러오는 중", "저장된 결과를 화면에 표시합니다.");

    const result = await fetchResult(minutes.minutes_id);
    progress.stop();
    renderResult(result, transcript, conversion.timings);
    setStep(null, stepOrder);
    progress.set("완료", "회의록과 변환 원본이 준비됐습니다.", 100);
    progress.addLog("결과 표시 완료");
    setBusy(false, "완료");
  } catch (error) {
    showError(error.message);
    progress.fail(error.message);
    setBusy(false, "실패");
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultOutput.textContent);
  resultMeta.textContent = "회의록 내용을 클립보드에 복사했습니다.";
});

downloadButton.addEventListener("click", downloadMarkdown);

progress.reset();
loadCapabilities();
