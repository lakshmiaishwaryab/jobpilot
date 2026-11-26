import httpx
import pytest

from app.services import llm
from app.services.matcher import analyze, cosine_similarity, extract_skills


def test_extract_skills_handles_aliases_and_symbols():
    skills = extract_skills("Built REST APIs in Python, C++ and Postgres; CI/CD via GitHub Actions; k8s")
    assert {"python", "c++", "postgresql", "rest apis", "ci/cd", "kubernetes"} <= skills


def test_java_does_not_match_javascript():
    assert "java" not in extract_skills("JavaScript developer")
    assert "javascript" in extract_skills("JavaScript developer")


def test_cosine_similarity_bounds():
    assert cosine_similarity(["a", "b"], ["a", "b"]) == pytest.approx(1.0)
    assert cosine_similarity(["a"], ["b"]) == 0.0
    assert cosine_similarity([], ["a"]) == 0.0


def test_better_resume_scores_higher():
    jd = "Python FastAPI Docker PostgreSQL REST APIs engineer"
    strong = analyze("Python developer building FastAPI REST APIs with Docker and PostgreSQL", jd)
    weak = analyze("Graphic designer skilled in Photoshop and illustration", jd)
    assert strong.score > weak.score
    assert strong.missing_skills == []


def test_rule_suggestions_mention_missing_skills():
    analysis = analyze("Python developer", "Python and Kubernetes engineer")
    tips = llm.rule_based_suggestions(analysis)
    assert any("kubernetes" in t for t in tips)


def test_llm_path_parses_json_and_falls_back(monkeypatch):
    monkeypatch.setattr(llm.get_settings(), "anthropic_api_key", "test-key")
    analysis = analyze("Python developer", "Python and Docker engineer")

    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, json={"content": [{"type": "text", "text": '["Tip one", "Tip two"]'}]})

    with httpx.Client(transport=httpx.MockTransport(ok_handler)) as c:
        assert llm.llm_suggestions("r", "j", analysis, client=c) == ["Tip one", "Tip two"]

    def fail_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(fail_handler)) as c:
        assert llm.llm_suggestions("r", "j", analysis, client=c) is None
