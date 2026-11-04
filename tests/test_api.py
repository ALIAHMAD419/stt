import pytest
pytest.importorskip("fastapi"); pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from app.api import app
from app import config
c = TestClient(app)
PAT = [("tone", 3), ("sil", 1), ("tone", 2)]

def test_upload_and_poll(mk):
    p = mk("a.mp3", PAT)
    r = c.post("/transcriptions", files={"file": ("a.mp3", p.read_bytes(), "audio/mpeg")})
    assert r.status_code == 202
    j = c.get(r.json()["links"]["status"]).json()          # TestClient runs background tasks before returning
    assert j["status"] == "done" and len(j["result"]["segments"]) == 2
    assert "-->" in c.get(f"/transcriptions/{j['id']}/srt").text

def test_rejects_bad_type_corrupt_empty_oversize(monkeypatch):
    assert c.post("/transcriptions", files={"file": ("x.txt", b"hi")}).status_code == 415
    assert c.post("/transcriptions", files={"file": ("x.mp3", b"garbage")}).status_code == 422
    assert c.post("/transcriptions", files={"file": ("x.mp3", b"")}).status_code == 400
    monkeypatch.setattr("app.api.MAX_BYTES", 10)
    assert c.post("/transcriptions", files={"file": ("x.mp3", b"x" * 100)}).status_code == 413

def test_unknown_job():
    assert c.get("/transcriptions/deadbeef").status_code == 404
