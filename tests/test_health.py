"""
Tests for GET /health

These tests run against the FastAPI TestClient — no live server is required.
Run:  pytest tests/test_health.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_returns_200():
    """The health endpoint must respond with HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_payload():
    """The health endpoint must return {"status": "ok"}."""
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


def test_health_content_type_is_json():
    """The response content-type must be application/json."""
    response = client.get("/health")
    assert "application/json" in response.headers["content-type"]
