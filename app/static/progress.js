window.createProgressView = function createProgressView(elements) {
  let timer = null;
  let startedAt = 0;

  function formatElapsed(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
  }

  function stop() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function set(title, detail, percent = null) {
    elements.title.textContent = title;
    elements.detail.textContent = detail;
    elements.bar.classList.remove("is-error");
    elements.bar.classList.toggle("is-indeterminate", percent === null);
    elements.bar.style.width = percent === null ? "38%" : `${percent}%`;
  }

  function addLog(message) {
    const item = document.createElement("li");
    item.textContent = message;
    elements.log.prepend(item);
  }

  function startTimed(title, detail) {
    stop();
    startedAt = Date.now();
    set(title, `${detail} · 경과 0:00`);
    timer = window.setInterval(() => {
      const elapsed = formatElapsed(Date.now() - startedAt);
      set(title, `${detail} · 경과 ${elapsed}`);
    }, 1000);
  }

  function setFromJob(job) {
    stop();
    const elapsed = startedAt > 0 ? ` · 경과 ${formatElapsed(Date.now() - startedAt)}` : "";
    set(stageTitle(job.stage), `${job.message || "처리 중입니다."}${elapsed}`, job.percent);
  }

  function renderTimings(timings) {
    if (!elements.timings) {
      return;
    }
    const items = normalizeTimings(timings);
    if (items.length === 0) {
      elements.timings.hidden = true;
      elements.timings.textContent = "";
      return;
    }
    const summary = items
      .map((item) => `${timingStageLabel(item.stage)} ${formatElapsed(item.seconds * 1000)}`)
      .join(" · ");
    elements.timings.hidden = false;
    elements.timings.textContent = `처리 시간 · ${summary}`;
  }

  function normalizeTimings(timings) {
    const entries = Array.isArray(timings) ? arrayTimingEntries(timings) : objectTimingEntries(timings);
    return entries
      .map(([stage, value]) => ({ seconds: timingSeconds(value), stage }))
      .filter((item) => item.stage && item.seconds !== null);
  }

  function arrayTimingEntries(timings) {
    return timings.map((item) => [
      item.stage || item.name || item.label || "",
      item,
    ]);
  }

  function objectTimingEntries(timings) {
    if (!timings || typeof timings !== "object") {
      return [];
    }
    return Object.entries(timings);
  }

  function timingSeconds(value) {
    if (typeof value === "number") {
      return value;
    }
    if (!value || typeof value !== "object") {
      return null;
    }
    if (typeof value.seconds === "number") {
      return value.seconds;
    }
    if (typeof value.duration_seconds === "number") {
      return value.duration_seconds;
    }
    if (typeof value.duration_ms === "number") {
      return value.duration_ms / 1000;
    }
    if (typeof value.milliseconds === "number") {
      return value.milliseconds / 1000;
    }
    return null;
  }

  function stageTitle(stage) {
    const titles = {
      aligning: "화자 시간 맞추는 중",
      completed: "변환 완료",
      converting: "음성 파일 준비 중",
      diarizing: "화자 구분 중",
      failed: "변환 실패",
      loading: "작업 확인 중",
      queued: "대기 중",
      recognizing: "음성을 텍스트로 변환 중",
      saving: "결과 저장 중",
    };
    return titles[stage] || "음성 변환 중";
  }

  function timingStageLabel(stage) {
    const labels = {
      aligning: "화자 정렬",
      completed: "완료",
      converting: "파일 준비",
      diarizing: "화자 구분",
      loading: "작업 확인",
      minutes: "회의록",
      recognizing: "음성 인식",
      saving: "저장",
      upload: "업로드",
    };
    return labels[stage] || stage;
  }

  function reset() {
    stop();
    elements.log.textContent = "";
    renderTimings(null);
    set("대기 중", "음성 파일을 선택하면 처리를 시작합니다.", 0);
  }

  function fail(message) {
    stop();
    set("실패", message, 100);
    elements.bar.classList.add("is-error");
    addLog("처리 실패");
  }

  return {
    addLog,
    fail,
    renderTimings,
    reset,
    set,
    setFromJob,
    startTimed,
    stop,
  };
};
