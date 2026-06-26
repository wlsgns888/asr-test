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

  function reset() {
    stop();
    elements.log.textContent = "";
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
    reset,
    set,
    startTimed,
    stop,
  };
};
