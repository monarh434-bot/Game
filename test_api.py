from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True

def test_join():
    res = client.post("/api/join", json={"nickname": "Tester"})
    assert res.status_code == 200
    assert res.json()["nickname"] == "Tester"

def test_block_update():
    res = client.post("/api/block", json={"x": 1, "y": 1, "z": 1, "block_type": "wood"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
