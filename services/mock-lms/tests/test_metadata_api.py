"""Canvas-style metadata API behavior (requirements §5.3)."""

import re

from fastapi.testclient import TestClient


def test_get_course(client: TestClient):
    r = client.get("/api/v1/courses/1001")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "1001"
    assert body["name"]
    # course_code is generated; assert the Canvas-style shape, not a literal value.
    assert re.fullmatch(r"[A-Z]+-\d+", body["course_code"])


def test_unknown_course_returns_canvas_style_404(client: TestClient):
    r = client.get("/api/v1/courses/9999")
    assert r.status_code == 404
    assert r.json()["detail"]["errors"][0]["message"]


def test_enrollments_filter_by_user(client: TestClient):
    r = client.get("/api/v1/courses/1001/enrollments", params={"user_id": "2001"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["user_id"] == "2001"


def test_modules_include_items_toggle(client: TestClient):
    without = client.get("/api/v1/courses/1001/modules").json()
    assert "items" not in without[0]
    with_items = client.get("/api/v1/courses/1001/modules", params={"include[]": "items"}).json()
    assert len(with_items[0]["items"]) == 2


def test_outcome_results_with_alignments(client: TestClient):
    r = client.get(
        "/api/v1/courses/1001/outcome_results",
        params={"user_ids[]": "2001", "outcome_ids[]": "3001", "include[]": "alignments"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome_results"][0]["mastery"] is True
    assert body["linked"]["alignments"][0]["assignment_id"] == "4001"


def test_submissions_filter(client: TestClient):
    r = client.get(
        "/api/v1/courses/1001/students/submissions",
        params={"student_ids[]": "2001", "assignment_ids[]": "4001"},
    )
    assert r.status_code == 200
    assert r.json()[0]["grade"] == "A"


def test_deterministic_responses(client: TestClient):
    first = client.get("/api/v1/courses/1001").json()
    second = client.get("/api/v1/courses/1001").json()
    assert first == second


def test_page_lookup(client: TestClient):
    r = client.get("/api/v1/courses/1001/pages/syllabus")
    assert r.status_code == 200
    assert r.json()["title"] == "Course Syllabus"
