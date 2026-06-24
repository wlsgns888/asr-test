from app.main import create_app
from fastapi.testclient import TestClient


def test_root_serves_frontend_shell() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "회의록 워크벤치" in response.text
    assert "원본 전사" in response.text
    assert "Markdown 다운로드" in response.text
    assert "/static/app.js" in response.text


def test_static_frontend_assets_are_served() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "fetch(" in response.text
    assert "downloadMarkdown" in response.text
