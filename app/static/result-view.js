function createResultView() {
  const resultOutput = document.querySelector("#result-output");
  const resultMeta = document.querySelector("#result-meta");
  const sourceOutput = document.querySelector("#source-output");
  const sourceMeta = document.querySelector("#source-meta");
  const minutesMeta = document.querySelector("#minutes-meta");
  const copySourceButton = document.querySelector("#copy-source-button");
  const downloadSourceButton = document.querySelector("#download-source-button");
  const copyMinutesButton = document.querySelector("#copy-minutes-button");
  const downloadMinutesButton = document.querySelector("#download-minutes-button");

  const state = {
    minutesId: "",
    minutesMarkdown: "",
    sourceMarkdown: "",
    sourceText: "",
    transcriptId: "",
  };
  const outputActionButtons = [
    copySourceButton,
    downloadSourceButton,
    copyMinutesButton,
    downloadMinutesButton,
  ];

  function setOutputActionsEnabled(isEnabled) {
    outputActionButtons.forEach((button) => {
      button.disabled = !isEnabled;
    });
  }

  function clearState() {
    state.minutesId = "";
    state.minutesMarkdown = "";
    state.sourceMarkdown = "";
    state.sourceText = "";
    state.transcriptId = "";
    setOutputActionsEnabled(false);
  }

  function clear() {
    resultOutput.textContent = "";
    sourceOutput.textContent = "";
    sourceMeta.textContent = "대기";
    minutesMeta.textContent = "대기";
    clearState();
  }

  function showError(message) {
    resultMeta.textContent = "오류가 발생했습니다.";
    resultOutput.textContent = message;
    sourceOutput.textContent = "";
    sourceMeta.textContent = "대기";
    minutesMeta.textContent = "실패";
    clearState();
  }

  function render(result, transcript) {
    resultMeta.textContent = `회의록 ID ${result.minutes_id} · 변환 ID ${transcript.transcript_id}`;
    sourceMeta.textContent = transcript.speaker_transcript
      ? `${transcript.language || "원본"} · 화자 구분`
      : transcript.language || "원본";
    state.sourceText =
      transcript.speaker_transcript || transcript.text || "(변환 원본 없음)";
    sourceOutput.textContent = state.sourceText;
    minutesMeta.textContent = "Markdown";
    resultOutput.textContent = result.markdown;
    state.transcriptId = transcript.transcript_id;
    state.sourceMarkdown = `# 원본 변환\n\n${state.sourceText}`;
    state.minutesMarkdown = result.markdown;
    state.minutesId = result.minutes_id;
    setOutputActionsEnabled(true);
  }

  function downloadContentAsMarkdown(content, fileName) {
    if (!content) {
      return;
    }

    const blob = new Blob([content], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.click();
    URL.revokeObjectURL(url);
  }

  function downloadSourceMarkdown() {
    const fileName = state.transcriptId
      ? `source-transcript-${state.transcriptId}.md`
      : "source-transcript.md";
    downloadContentAsMarkdown(state.sourceMarkdown, fileName);
  }

  function downloadMinutesMarkdown() {
    const fileName = state.minutesId
      ? `meeting-minutes-${state.minutesId}.md`
      : "meeting-minutes.md";
    downloadContentAsMarkdown(state.minutesMarkdown, fileName);
  }

  async function copyContent(content, successMessage) {
    if (!content) {
      return;
    }

    await navigator.clipboard.writeText(content);
    resultMeta.textContent = successMessage;
  }

  copySourceButton.addEventListener("click", async () => {
    await copyContent(state.sourceText, "원본 변환 내용을 클립보드에 복사했습니다.");
  });

  copyMinutesButton.addEventListener("click", async () => {
    await copyContent(state.minutesMarkdown, "회의록 내용을 클립보드에 복사했습니다.");
  });

  downloadSourceButton.addEventListener("click", downloadSourceMarkdown);
  downloadMinutesButton.addEventListener("click", downloadMinutesMarkdown);

  clearState();
  return {
    clear,
    render,
    showError,
  };
}

window.createResultView = createResultView;
