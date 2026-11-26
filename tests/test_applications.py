from datetime import date, timedelta

from tests.conftest import register_and_login

RESUME = (
    "Backend developer with Python, FastAPI, SQL and REST APIs. Built services on Linux "
    "with Git and Docker. Experience in Java and unit testing with pytest."
)
JD = (
    "We need a backend engineer with Python, FastAPI, PostgreSQL, Docker and Kubernetes. "
    "You will build REST APIs and write unit tests."
)


def make(client, auth, **overrides):
    body = {"company": "Acme", "role": "Backend Engineer", **overrides}
    r = client.post("/applications", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_crud_flow(client, auth):
    created = make(client, auth, location="Remote")
    assert created["status"] == "applied"
    assert created["applied_on"] == date.today().isoformat()

    app_id = created["id"]
    r = client.patch(f"/applications/{app_id}", json={"status": "interview", "notes": "Round 1 Fri"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "interview"
    assert r.json()["location"] == "Remote"  # untouched field kept

    assert client.get(f"/applications/{app_id}", headers=auth).status_code == 200
    assert client.delete(f"/applications/{app_id}", headers=auth).status_code == 204
    assert client.get(f"/applications/{app_id}", headers=auth).status_code == 404


def test_wishlist_has_no_applied_date(client, auth):
    assert make(client, auth, status="wishlist")["applied_on"] is None


def test_list_filter_search_and_pagination(client, auth):
    make(client, auth, company="Stripe", role="Backend Engineer")
    make(client, auth, company="Notion", role="Platform Engineer", status="rejected")
    make(client, auth, company="Stripe", role="Data Engineer", status="interview")

    page = client.get("/applications", params={"q": "stripe"}, headers=auth).json()
    assert page["total"] == 2

    rejected = client.get("/applications", params={"status": "rejected"}, headers=auth).json()
    assert [a["company"] for a in rejected["items"]] == ["Notion"]

    first = client.get("/applications", params={"limit": 2}, headers=auth).json()
    assert first["total"] == 3 and len(first["items"]) == 2


def test_users_cannot_see_each_others_data(client, auth):
    mine = make(client, auth)
    other = register_and_login(client, "other@example.com")
    assert client.get(f"/applications/{mine['id']}", headers=other).status_code == 404
    assert client.get("/applications", headers=other).json()["total"] == 0


def test_stats(client, auth):
    make(client, auth, status="wishlist")
    make(client, auth, status="applied")
    make(client, auth, status="interview")
    make(client, auth, status="rejected")
    s = client.get("/applications/stats", headers=auth).json()
    assert s["total"] == 4
    assert s["by_status"]["wishlist"] == 1
    assert s["response_rate"] == round(2 / 3, 3)


def test_follow_ups(client, auth):
    old = (date.today() - timedelta(days=10)).isoformat()
    stale = make(client, auth, company="Old Co", applied_on=old)
    make(client, auth, company="New Co")
    make(client, auth, company="Moved On", applied_on=old, status="rejected")
    due = client.get("/applications/follow-ups", headers=auth).json()
    assert [a["id"] for a in due] == [stale["id"]]


def test_match_requires_resume_and_jd(client, auth):
    app_id = make(client, auth, job_description=JD)["id"]
    assert client.post(f"/applications/{app_id}/match", headers=auth).status_code == 400

    client.put("/auth/me/resume", json={"resume_text": RESUME}, headers=auth)
    no_jd = make(client, auth)["id"]
    assert client.post(f"/applications/{no_jd}/match", headers=auth).status_code == 400


def test_match_scores_and_saves(client, auth):
    client.put("/auth/me/resume", json={"resume_text": RESUME}, headers=auth)
    app_id = make(client, auth, job_description=JD)["id"]
    result = client.post(f"/applications/{app_id}/match", headers=auth).json()

    assert "python" in result["matched_skills"]
    assert "kubernetes" in result["missing_skills"]
    assert 0 < result["score"] <= 100
    assert result["suggestions_source"] == "rules"  # no API key in tests
    assert client.get(f"/applications/{app_id}", headers=auth).json()["match_score"] == result["score"]
    assert client.get("/applications/stats", headers=auth).json()["average_match_score"] == result["score"]


def test_editing_jd_clears_stale_score(client, auth):
    client.put("/auth/me/resume", json={"resume_text": RESUME}, headers=auth)
    app_id = make(client, auth, job_description=JD)["id"]
    client.post(f"/applications/{app_id}/match", headers=auth)
    r = client.patch(f"/applications/{app_id}", json={"job_description": "Go and Rust engineer needed"}, headers=auth)
    assert r.json()["match_score"] is None


def test_ai_match_endpoint_and_health(client, auth):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.post("/ai/match", json={"resume_text": RESUME, "job_description": JD}, headers=auth)
    assert r.status_code == 200
    assert "docker" in r.json()["matched_skills"]
