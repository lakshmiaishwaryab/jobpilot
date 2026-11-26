"""Resume <-> job description matching.

Two signals are blended into a 0-100 score:
  1. Skill coverage: which known skills the job asks for that the resume has.
  2. Text similarity: cosine similarity of the two texts' term-frequency vectors,
     so wording overlap beyond the skill list still counts.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

# Canonical skill -> aliases that should count as the same skill.
SKILLS: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "go": ("golang",),
    "c++": ("c++", "cpp"),
    "sql": ("sql",),
    "postgresql": ("postgresql", "postgres"),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo"),
    "redis": ("redis",),
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "spring boot": ("spring boot", "springboot", "spring"),
    "rest apis": ("rest api", "rest apis", "restful"),
    "graphql": ("graphql",),
    "microservices": ("microservices", "microservice"),
    "docker": ("docker", "containers"),
    "kubernetes": ("kubernetes", "k8s"),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure",),
    "gcp": ("gcp", "google cloud"),
    "linux": ("linux", "unix"),
    "git": ("git", "github", "gitlab"),
    "ci/cd": ("ci/cd", "cicd", "github actions", "jenkins"),
    "unit testing": ("unit testing", "pytest", "junit", "unit tests"),
    "machine learning": ("machine learning", "ml"),
    "llm": ("llm", "llms", "large language model", "genai", "generative ai"),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "opencv": ("opencv",),
    "sap abap": ("abap", "sap abap"),
    "sap rap": ("sap rap", "restful abap"),
    "react": ("react", "reactjs"),
    "data structures": ("data structures", "algorithms", "dsa"),
    "agile": ("agile", "scrum"),
}

STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the to with we you "
    "your our will this who what can able experience years year strong good work working team "
    "role job candidate candidates using use including etc".split()
)

_TOKEN = re.compile(r"[a-z][a-z0-9+#./-]*")


@dataclass(frozen=True)
class MatchAnalysis:
    score: int
    matched_skills: list[str]
    missing_skills: list[str]


def tokenize(text: str) -> list[str]:
    return [t.strip("./-") for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


def extract_skills(text: str) -> set[str]:
    lowered = f" {text.lower()} "
    found = set()
    for skill, aliases in SKILLS.items():
        for alias in aliases:
            # word-boundary match that still allows symbols like "c++" and "ci/cd"
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9+])", lowered):
                found.add(skill)
                break
    return found


def cosine_similarity(a: list[str], b: list[str]) -> float:
    ca, cb = Counter(a), Counter(b)
    dot = sum(ca[t] * cb[t] for t in ca.keys() & cb.keys())
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


def analyze(resume_text: str, job_description: str) -> MatchAnalysis:
    resume_skills = extract_skills(resume_text)
    job_skills = extract_skills(job_description)

    matched = sorted(job_skills & resume_skills)
    missing = sorted(job_skills - resume_skills)

    coverage = len(matched) / len(job_skills) if job_skills else 0.0
    similarity = cosine_similarity(tokenize(resume_text), tokenize(job_description))

    # Skills matter most; text similarity rewards relevant wording beyond them.
    weight = 0.75 if job_skills else 0.0
    raw = weight * coverage + (1 - weight) * similarity
    score = round(min(raw, 1.0) * 100)
    return MatchAnalysis(score=score, matched_skills=matched, missing_skills=missing)
