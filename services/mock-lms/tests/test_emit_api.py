"""Event emission + scenario behavior (requirements §5.1, §5.4)."""

from fastapi.testclient import TestClient


def test_emit_single_skill_mastered(client: TestClient):
    r = client.post(
        "/demo/emit",
        json={
            "event_type": "skill_mastered",
            "course_id": "1001",
            "user_id": "2001",
            "outcome_id": "3001",
            "assignment_id": "4001",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["correlation_id"].startswith("corr_")
    env = body["envelope"]
    # Canvas live-event name, not our internal type:
    assert env["metadata"]["event_name"] == "learning_outcome_result_created"
    assert env["metadata"]["context_id"] == "1001"
    assert env["body"]["mastery"] is True
    assert env["body"]["learning_outcome_id"] == "3001"


def test_emit_unknown_id_is_rejected(client: TestClient):
    r = client.post(
        "/demo/emit",
        json={"event_type": "skill_mastered", "course_id": "1001", "user_id": "nope",
              "outcome_id": "3001"},
    )
    assert r.status_code == 422
    assert "user_id" in r.json()["detail"]


def test_list_scenarios(client: TestClient):
    ids = {s["id"] for s in client.get("/demo/scenarios").json()}
    assert {"skill-mastered", "course-completed", "badge-awarded"} <= ids


def test_run_scenario_stamps_one_correlation_id(client: TestClient):
    r = client.post("/demo/scenarios/skill-mastered/run")
    assert r.status_code == 200
    body = r.json()
    assert len(body["emissions"]) == 1
    env = body["emissions"][0]["envelope"]
    assert env["metadata"]["correlation_id"] == body["correlation_id"]
    assert env["metadata"]["scenario_id"] == "skill-mastered"


def test_scenario_reruns_produce_fresh_ids(client: TestClient):
    first = client.post("/demo/scenarios/skill-mastered/run").json()
    second = client.post("/demo/scenarios/skill-mastered/run").json()
    e1 = first["emissions"][0]["envelope"]["metadata"]
    e2 = second["emissions"][0]["envelope"]["metadata"]
    assert e1["event_id"] != e2["event_id"]
    assert first["correlation_id"] != second["correlation_id"]


def test_all_happy_paths_emit_valid_events(client: TestClient):
    for scenario_id, expected_name in [
        ("skill-mastered", "learning_outcome_result_created"),
        ("course-completed", "course_completed"),
        ("badge-awarded", "badge_awarded"),
    ]:
        body = client.post(f"/demo/scenarios/{scenario_id}/run").json()
        assert body["emissions"][0]["envelope"]["metadata"]["event_name"] == expected_name


def test_emissions_log_incremental_cursor(client: TestClient):
    client.post("/demo/scenarios/badge-awarded/reset")  # clear log
    client.post("/demo/scenarios/skill-mastered/run")
    first = client.get("/demo/emissions").json()
    assert first["cursor"] >= 1
    # Nothing new since the latest cursor:
    tail = client.get("/demo/emissions", params={"since": first["cursor"]}).json()
    assert tail["emissions"] == []


def test_run_unknown_scenario_404(client: TestClient):
    assert client.post("/demo/scenarios/nope/run").status_code == 404
