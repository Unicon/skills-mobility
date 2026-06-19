"""Emission control API: courses, Actions, and the events they emit (design §2/§4)."""

from fastapi.testclient import TestClient


def _courses(client: TestClient) -> list[dict]:
    r = client.get("/demo/courses")
    assert r.status_code == 200
    return r.json()


def _by_kind(courses: list[dict], kind: str) -> dict:
    return next(c for c in courses if c["kind"] == kind)


def test_list_courses_exposes_actions_and_learners(client: TestClient):
    courses = _courses(client)
    kinds = {c["kind"] for c in courses}
    assert {"standard", "digital_credential"} <= kinds
    for course in courses:
        assert course["actions"], "every course offers grading Actions"
        assert all(a["event_type"] for a in course["actions"])
        assert all(learner["email"] for learner in course["learners"])


def test_run_skill_mastered_happy_path(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    r = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m1", "scope": "one"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["correlation_id"].startswith("corr_")
    assert len(body["emitted"]) == 1
    env = body["emitted"][0]
    assert env["metadata"]["event_name"] == "learning_outcome_result_created"
    assert env["metadata"]["correlation_id"] == body["correlation_id"]
    assert env["metadata"]["action_id"] == f"{std['id']}-grade-m1"
    assert env["body"]["mastery"] is True


def test_skill_mastered_competency_vs_sub_competency(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    happy = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m1", "scope": "one"},
    ).json()
    edge = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m2", "scope": "one"},
    ).json()
    # Happy path = competency outcome (title "N.0.0"); edge = sub-competency
    # (title "N.M.0"). The title is the signal carried on the event.
    assert happy["emitted"][0]["body"]["title"].startswith("1.0.0 ")
    assert edge["emitted"][0]["body"]["title"].startswith("1.2.0 ")
    assert edge["emitted"][0]["metadata"]["event_name"] == "learning_outcome_result_created"


def test_reruns_produce_fresh_ids_over_stable_correlation(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    payload = {"action_id": f"{std['id']}-grade-m1", "scope": "one"}
    first = client.post(f"/demo/courses/{std['id']}/actions", json=payload).json()
    second = client.post(f"/demo/courses/{std['id']}/actions", json=payload).json()
    assert first["correlation_id"] != second["correlation_id"]
    first_event_id = first["emitted"][0]["metadata"]["event_id"]
    second_event_id = second["emitted"][0]["metadata"]["event_id"]
    assert first_event_id != second_event_id


def test_course_completed_passing_vs_failing_learner(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    action = f"{std['id']}-grade-final"
    passing, failing = std["learners"][0]["id"], std["learners"][1]["id"]

    p = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": action, "scope": "one", "user_id": passing},
    ).json()
    f = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": action, "scope": "one", "user_id": failing},
    ).json()
    # The event carries the final score; passing vs failing is a downstream
    # judgment, not a boolean on the event.
    assert p["emitted"][0]["body"]["final_score"] >= 60
    assert f["emitted"][0]["body"]["final_score"] < 60
    assert f["emitted"][0]["metadata"]["event_name"] == "course_completed"


def test_badge_awarded_omits_acceptance_discovered_via_get(client: TestClient):
    dc = _by_kind(_courses(client), "digital_credential")
    happy = client.post(
        f"/demo/courses/{dc['id']}/actions",
        json={"action_id": f"{dc['id']}-grade-m1", "scope": "one"},
    ).json()
    edge = client.post(
        f"/demo/courses/{dc['id']}/actions",
        json={"action_id": f"{dc['id']}-grade-m2", "scope": "one"},
    ).json()
    # Acceptance is NOT carried on the event — a consumer must discover it by
    # fetching the badge (GET badge by id), which 200s for an accepted badge
    # and 409s for an unaccepted one.
    assert "accepted" not in happy["emitted"][0]["body"]
    assert "accepted" not in edge["emitted"][0]["body"]
    assert edge["emitted"][0]["metadata"]["event_name"] == "badge_awarded"

    happy_badge = happy["emitted"][0]["body"]["badge_id"]
    edge_badge = edge["emitted"][0]["body"]["badge_id"]
    assert client.get(f"/api/v1/badges/{happy_badge}").status_code == 200
    assert client.get(f"/api/v1/badges/{edge_badge}").status_code == 409


def test_scope_all_emits_one_event_per_enrolled_learner(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    r = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m1", "scope": "all"},
    ).json()
    assert len(r["emitted"]) == len(std["learners"])
    # One shared correlation id across the bulk run.
    corr = {e["metadata"]["correlation_id"] for e in r["emitted"]}
    assert corr == {r["correlation_id"]}


def test_unknown_course_and_action_return_404(client: TestClient):
    assert client.post("/demo/courses/NOPE/actions", json={"action_id": "x"}).status_code == 404
    std = _by_kind(_courses(client), "standard")
    bad = client.post(f"/demo/courses/{std['id']}/actions", json={"action_id": "no-such-action"})
    assert bad.status_code == 404


def test_unknown_learner_is_rejected(client: TestClient):
    std = _by_kind(_courses(client), "standard")
    r = client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m1", "scope": "one", "user_id": "ghost"},
    )
    assert r.status_code == 422


def test_reset_ok(client: TestClient):
    assert client.post("/demo/reset").json() == {"ok": True}
