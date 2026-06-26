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
    assert "Markdown 다운로드" in response.text
    assert "/static/app.js" in response.text


def test_static_frontend_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "fetch(" in response.text
    assert "downloadMarkdown" in response.text


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
