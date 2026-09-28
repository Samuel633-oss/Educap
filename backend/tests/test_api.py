from fastapi.testclient import TestClient
from main import app


def _client():
    return TestClient(app)


def test_api_flow_and_isolation(llm):
    c = _client()
    a = c.post("/api/students", json={"name": "Alex"}).json()["id"]
    b = c.post("/api/students", json={"name": "Bea"}).json()["id"]
    assert c.get("/api/health").json()["ok"]
    r = c.post("/api/chat", json={"student_id": a, "message": "Teach me photosynthesis"}).json()
    assert r["agent"] == "tutor"
    cid = r["conversation_id"]
    # Bea cannot read or write into Alex's conversation
    assert c.post("/api/chat", json={"student_id": b, "message": "hi", "conversation_id": cid}).status_code == 403
    assert c.get(f"/api/students/{b}/conversations/{cid}").status_code == 404
    assert len(c.get(f"/api/students/{a}/conversations/{cid}").json()) == 2
    # documents are private
    d = c.post(f"/api/students/{a}/documents", json={"title": "N", "text": "The Calvin cycle occurs in the stroma. " * 5}).json()
    assert d["chunks"] >= 1
    assert c.get(f"/api/students/{b}/documents").json() == []
    assert c.delete(f"/api/students/{b}/documents/{d['id']}").status_code == 404
    up = c.post(f"/api/students/{a}/documents/upload", files={"file": ("x.txt", b"Krebs cycle happens in the mitochondrial matrix. " * 4)})
    assert up.status_code == 200
    assert len(c.get("/api/tools").json()) >= 8


def test_stream_endpoint(llm):
    c = _client()
    a = c.post("/api/students", json={"name": "Alex"}).json()["id"]
    with c.stream("POST", "/api/chat/stream", json={"student_id": a, "message": "Quiz me on photosynthesis"}) as r:
        events = [__import__("json").loads(l) for l in r.iter_lines() if l]
    assert events[0]["type"] == "status" and events[0]["agent"] == "exam"
    assert events[-1]["type"] == "final"
