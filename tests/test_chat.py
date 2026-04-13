from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_returns_answer_on_valid_request():
    """
    正常系テスト：
    有効なリクエストを送ったときに、200でレスポンスが返り、
    answerキーが含まれていることを確認する
    """
    response = client.post("/chat", json={
        "summary": "テストデータ",
        "question": "改善点は？"
    })

    assert response.status_code == 200
    assert "answer" in response.json()

def test_chat_handles_empty_input():
    """
    異常系テスト：
    空のデータを送信した場合に400エラーが返ることを確認する
    """
    response = client.post("/chat", json={
        "summary": "",
        "question": ""
    })

    assert response.status_code == 400
    assert "error" in response.json()