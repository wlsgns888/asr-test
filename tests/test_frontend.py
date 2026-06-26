import shutil
import subprocess

from app.main import create_app
from fastapi.testclient import TestClient


def test_root_serves_frontend_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "회의록 워크벤치" in response.text
    assert "원본 변환" in response.text
    assert "전사" not in response.text
    assert "50분 음성" in response.text
    assert "화자 구분 사용" in response.text
    assert 'id="speaker-separation-enabled"' in response.text
    assert "요약 프롬프트" in response.text
    assert 'id="summary-prompt"' in response.text
    assert "전문 회의록으로 요약하세요" in response.text
    assert "액션아이템(담당자/기한이 언급된 경우 포함)" in response.text
    assert "처리 시간" in response.text
    assert "Markdown 다운로드" in response.text
    assert "/static/payloads.js" in response.text
    assert "/static/app.js" in response.text


def test_static_frontend_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "fetch(" in response.text
    assert "downloadMarkdown" in response.text


def test_frontend_payload_helpers_send_new_backend_contract() -> None:
    node = shutil.which("node")
    if node is None:
        msg = "node is required for frontend payload behavior test"
        raise RuntimeError(msg)

    script_lines = [
        'const fs = require("node:fs");',
        'const vm = require("node:vm");',
        'const code = fs.readFileSync("app/static/payloads.js", "utf8");',
        "const context = { window: {} };",
        "vm.createContext(context);",
        "vm.runInContext(code, context);",
        "const conversion = context.window.createConversionJobPayload(",
        '  "upload-123",',
        "  true,",
        ");",
        "const minutes = context.window.createMinutesPayload(",
        '  "transcript-456",',
        '  "- 결정사항",',
        '  "실행 중심으로 요약",',
        ");",
        'if (conversion.upload_id !== "upload-123") {',
        "  throw new Error(`unexpected upload id: ${conversion.upload_id}`);",
        "}",
        "if (conversion.speaker_separation_enabled !== true) {",
        '  throw new Error("speaker separation flag missing");',
        "}",
        'if (minutes.transcript_id !== "transcript-456") {',
        "  throw new Error(`unexpected transcript id: ${minutes.transcript_id}`);",
        "}",
        'if (minutes.template !== "- 결정사항") {',
        "  throw new Error(`unexpected template: ${minutes.template}`);",
        "}",
        'if (minutes.summary_prompt !== "실행 중심으로 요약") {',
        "  throw new Error(`unexpected summary prompt: ${minutes.summary_prompt}`);",
        "}",
    ]
    completed = subprocess.run(  # noqa: S603
        [node, "-e", "\n".join(script_lines)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""


def test_job_progress_updates_stop_generic_timer() -> None:
    node = shutil.which("node")
    if node is None:
        msg = "node is required for frontend progress behavior test"
        raise RuntimeError(msg)

    script_lines = [
        'const fs = require("node:fs");',
        'const vm = require("node:vm");',
        'const code = fs.readFileSync("app/static/progress.js", "utf8");',
        "const intervals = new Map();",
        "let nextTimer = 1;",
        "const makeElement = () => ({",
        "  classList: { add() {}, remove() {}, toggle() {} },",
        "  prepend() {},",
        "  style: {},",
        '  textContent: "",',
        "});",
        "const context = {",
        "  window: {",
        "    setInterval(callback) {",
        "      const id = nextTimer++;",
        "      intervals.set(id, callback);",
        "      return id;",
        "    },",
        "    clearInterval(id) {",
        "      intervals.delete(id);",
        "    },",
        "  },",
        "};",
        "vm.createContext(context);",
        "vm.runInContext(code, context);",
        "const elements = {",
        "  bar: makeElement(),",
        "  detail: makeElement(),",
        "  log: makeElement(),",
        "  title: makeElement(),",
        "};",
        "const progress = context.window.createProgressView(elements);",
        'progress.startTimed("음성 변환 중", "일반 타이머");',
        "progress.setFromJob({",
        '  stage: "recognizing",',
        '  message: "서버 단계 표시",',
        "  percent: 35,",
        "});",
        "for (const callback of intervals.values()) {",
        "  callback();",
        "}",
        'if (elements.title.textContent !== "음성을 텍스트로 변환 중") {',
        "  throw new Error(`unexpected title: ${elements.title.textContent}`);",
        "}",
        'if (!elements.detail.textContent.includes("서버 단계 표시")) {',
        "  throw new Error(`unexpected detail: ${elements.detail.textContent}`);",
        "}",
        'if (elements.bar.style.width !== "35%") {',
        "  throw new Error(`unexpected width: ${elements.bar.style.width}`);",
        "}",
        "if (intervals.size !== 0) {",
        "  throw new Error(`timer still active: ${intervals.size}`);",
        "}",
    ]
    script = "\n".join(script_lines)
    completed = subprocess.run(  # noqa: S603
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""


def test_job_progress_renders_timing_breakdown() -> None:
    node = shutil.which("node")
    if node is None:
        msg = "node is required for frontend timing behavior test"
        raise RuntimeError(msg)

    script_lines = [
        'const fs = require("node:fs");',
        'const vm = require("node:vm");',
        'const code = fs.readFileSync("app/static/progress.js", "utf8");',
        "const makeElement = () => ({",
        "  classList: { add() {}, remove() {}, toggle() {} },",
        "  hidden: false,",
        "  prepend() {},",
        "  style: {},",
        '  textContent: "",',
        "});",
        "const context = {",
        "  window: {",
        "    clearInterval() {},",
        "    setInterval() { return 1; },",
        "  },",
        "};",
        "vm.createContext(context);",
        "vm.runInContext(code, context);",
        "const elements = {",
        "  bar: makeElement(),",
        "  detail: makeElement(),",
        "  log: makeElement(),",
        "  timings: makeElement(),",
        "  title: makeElement(),",
        "};",
        "const progress = context.window.createProgressView(elements);",
        "progress.renderTimings({",
        "  recognizing: 83.6,",
        "  diarizing: { duration_ms: 2100 },",
        "  saving: { seconds: 1.2 },",
        "});",
        "if (elements.timings.hidden) {",
        '  throw new Error("timing breakdown is hidden");',
        "}",
        'if (!elements.timings.textContent.includes("처리 시간")) {',
        "  throw new Error(`missing heading: ${elements.timings.textContent}`);",
        "}",
        'if (!elements.timings.textContent.includes("음성 인식 1:23")) {',
        "  throw new Error(elements.timings.textContent);",
        "}",
        'if (!elements.timings.textContent.includes("화자 구분 0:02")) {',
        "  throw new Error(elements.timings.textContent);",
        "}",
        "progress.renderTimings([]);",
        'if (!elements.timings.hidden || elements.timings.textContent !== "") {',
        '  throw new Error("empty timings should clear the breakdown");',
        "}",
    ]
    completed = subprocess.run(  # noqa: S603
        [node, "-e", "\n".join(script_lines)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
