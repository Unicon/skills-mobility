"""LMS Resource APIs — Canvas-style read behavior (design §3, requirements §5.3)."""

from fastapi.testclient import TestClient


def _standard_course(client: TestClient) -> dict:
    courses = client.get("/demo/courses").json()
    return next(c for c in courses if c["kind"] == "standard")


def _dc_course(client: TestClient) -> dict:
    courses = client.get("/demo/courses").json()
    return next(c for c in courses if c["kind"] == "digital_credential")


def test_get_course(client: TestClient):
    course = _standard_course(client)
    r = client.get(f"/api/v1/courses/{course['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == course["id"]
    assert body["name"] and body["kind"] == "standard"


def test_unknown_course_returns_canvas_style_404(client: TestClient):
    r = client.get("/api/v1/courses/NOPE-000")
    assert r.status_code == 404
    assert r.json()["detail"]["errors"][0]["message"]


def test_enrollments_filter_by_user(client: TestClient):
    course = _standard_course(client)
    uid = course["learners"][0]["id"]
    r = client.get(f"/api/v1/courses/{course['id']}/enrollments", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["user_id"] == uid


def test_modules_include_items_toggle(client: TestClient):
    course = _standard_course(client)
    without = client.get(f"/api/v1/courses/{course['id']}/modules").json()
    assert without and "items" not in without[0]
    with_items = client.get(
        f"/api/v1/courses/{course['id']}/modules", params={"include[]": "items"}
    ).json()
    assert with_items[0]["items"]


def test_outcome_results_with_alignments(client: TestClient):
    course = _standard_course(client)
    cid, uid = course["id"], course["learners"][0]["id"]
    outcome_id = f"{cid}-OUT-1"  # the competency outcome
    r = client.get(
        f"/api/v1/courses/{cid}/outcome_results",
        params={"user_ids[]": uid, "outcome_ids[]": outcome_id, "include[]": "alignments"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["outcome_results"][0]["mastery"] is True
    assert body["linked"]["alignments"]


def test_submissions_filter(client: TestClient):
    course = _standard_course(client)
    cid, uid = course["id"], course["learners"][0]["id"]
    r = client.get(
        f"/api/v1/courses/{cid}/students/submissions",
        params={"student_ids[]": uid, "assignment_ids[]": f"{cid}-A-FINAL"},
    )
    assert r.status_code == 200
    assert r.json()[0]["grade"]


def test_rubrics(client: TestClient):
    course = _standard_course(client)
    r = client.get(f"/api/v1/courses/{course['id']}/rubrics")
    assert r.status_code == 200
    rubrics = r.json()
    assert rubrics and rubrics[0]["criteria"]


def test_user_profile_exposes_email(client: TestClient):
    course = _standard_course(client)
    uid = course["learners"][0]["id"]
    r = client.get(f"/api/v1/users/{uid}/profile")
    assert r.status_code == 200
    assert "@" in r.json()["email"]


def test_get_badge_accepted_vs_unaccepted(client: TestClient):
    dc = _dc_course(client)
    accepted = client.get(f"/api/v1/badges/{dc['id']}-BADGE-ACCEPTED")
    unaccepted = client.get(f"/api/v1/badges/{dc['id']}-BADGE-UNACCEPTED")
    unknown = client.get("/api/v1/badges/NOPE")
    assert accepted.status_code == 200 and accepted.json()["accepted"] is True
    # Unaccepted badges are not fetchable — the planner's acceptance gate.
    assert unaccepted.status_code == 409
    assert unknown.status_code == 404


def test_page_lookup(client: TestClient):
    course = _standard_course(client)
    r = client.get(f"/api/v1/courses/{course['id']}/pages/syllabus")
    assert r.status_code == 200
    assert r.json()["title"] == "Course Syllabus"


def test_deterministic_responses(client: TestClient):
    course = _standard_course(client)
    first = client.get(f"/api/v1/courses/{course['id']}").json()
    second = client.get(f"/api/v1/courses/{course['id']}").json()
    assert first == second
