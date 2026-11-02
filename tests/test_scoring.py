from types import SimpleNamespace

import httpx

from app.services import github
from app.services.github import build_evidence, skills_from_package_json, skills_from_requirements
from app.services.matching import job_matches, readiness, skill_gaps
from app.services.trust import score_skill, status_for

DEMAND = [
    {"name": "Python", "category": "Languages", "count": 8, "share": 80},
    {"name": "Docker", "category": "DevOps & Cloud", "count": 4, "share": 40},
    {"name": "AWS", "category": "DevOps & Cloud", "count": 2, "share": 20},
]


def test_a_resume_claim_alone_is_never_verified():
    assert status_for(score_skill(True, False, 0, False)) == "unverified"
    assert status_for(score_skill(True, True, 0, False)) == "partial"


def test_github_evidence_verifies_a_claim():
    assert status_for(score_skill(True, True, 1, True)) == "verified"
    assert score_skill(True, True, 5, True) == 100


def test_old_repositories_score_lower_than_recent_ones():
    assert score_skill(True, True, 2, False) < score_skill(True, True, 2, True)


def test_github_skill_missing_from_the_resume_is_only_partial():
    assert status_for(score_skill(False, False, 3, True)) == "partial"


def test_recent_bonus_needs_a_repository():
    assert score_skill(True, False, 0, True) == score_skill(True, False, 0, False)


def test_readiness_discounts_unproven_claims_but_coverage_does_not():
    scores = readiness({"Python": 30, "Docker": 100}, DEMAND)
    assert scores["coverage"] == round(100 * 120 / 140)
    assert scores["readiness"] == round(100 * (80 * 0.3 + 40) / 140)
    assert scores["readiness"] < scores["coverage"]


def test_readiness_is_zero_without_market_data():
    assert readiness({"Python": 100}, []) == {"readiness": 0, "coverage": 0}


def test_gaps_separate_missing_from_weak_and_include_resources():
    gaps = skill_gaps({"Python": 30, "Docker": 90}, DEMAND)
    assert [g["name"] for g in gaps["missing"]] == ["AWS"]
    assert [g["name"] for g in gaps["weak"]] == ["Python"]
    assert all(g["resources"] for g in gaps["missing"] + gaps["weak"])


def job(id, skills):
    return SimpleNamespace(
        id=id, title="Job", company="Co", location="", seniority="", apply_url=None, source="himalayas",
        source_url=None, published_at=None, skills=skills,
    )


def test_job_matches_rank_by_trust_and_skip_jobs_with_too_few_skills():
    results = job_matches(
        [job(1, ["Python", "Docker", "AWS"]), job(2, ["Python", "Java", "Rust"]), job(3, ["Python"])],
        {"Python": 90, "Docker": 90, "AWS": 30},
    )
    assert [r["id"] for r in results] == [1, 2]
    assert results[0]["matched"] == ["Python", "Docker"]
    assert results[0]["unproven"] == ["AWS"]
    assert results[1]["missing"] == ["Java", "Rust"]


def test_reads_skills_from_manifests():
    package = '{"dependencies": {"react": "19", "mongoose": "8"}, "devDependencies": {"jest": "30", "left-pad": "1"}}'
    assert skills_from_package_json(package) == {"React", "MongoDB", "Jest"}
    assert skills_from_package_json("not json") == set()
    assert skills_from_package_json("[]") == set()
    assert skills_from_requirements("fastapi==0.1\n# comment\ntorch>=2\npsycopg2-binary\n") == {
        "FastAPI", "PyTorch", "PostgreSQL",
    }


def test_build_evidence_merges_languages_topics_and_scans():
    repos = [
        {"name": "a", "full_name": "u/a", "html_url": "https://g/a", "language": "Jupyter Notebook", "topics": ["docker"], "pushed_at": None},
        {"name": "b", "full_name": "u/b", "html_url": "https://g/b", "language": "Python", "topics": [], "pushed_at": None},
    ]
    evidence = build_evidence(repos, {"u/a": {"React": "dependency"}})
    assert len(evidence["Python"]) == 2
    assert evidence["Docker"][0]["signal"] == "topic"
    assert evidence["React"][0]["signal"] == "dependency"


def test_manifests_fall_back_to_the_api_when_raw_host_is_blocked(monkeypatch):
    monkeypatch.setattr(github, "_raw_retry_at", 0.0)
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "raw.githubusercontent.com":
            raise httpx.ConnectTimeout("blocked")
        if request.url.path.endswith("/contents"):
            return httpx.Response(200, json=[{"name": "package.json", "type": "file"}, {"name": "src", "type": "dir"}])
        return httpx.Response(200, text='{"dependencies": {"react": "19"}}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    repo = {"full_name": "u/a", "default_branch": "main"}

    assert github._read_manifests(client, repo) == {"package.json": '{"dependencies": {"react": "19"}}'}
    assert hosts.count("raw.githubusercontent.com") == 1
    assert hosts.count("api.github.com") == 2

    # Once blocked, the next repository skips the raw host and its connection timeout.
    github._read_manifests(client, repo)
    assert hosts.count("raw.githubusercontent.com") == 1


def test_manifests_use_the_raw_host_when_it_works(monkeypatch):
    monkeypatch.setattr(github, "_raw_retry_at", 0.0)

    def handler(request):
        assert request.url.host == "raw.githubusercontent.com"
        return httpx.Response(200, text="x") if request.url.path.endswith("Dockerfile") else httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert github._read_manifests(client, {"full_name": "u/a", "default_branch": "main"}) == {"Dockerfile": "x"}


def test_repositories_prove_git_and_frameworks_prove_their_foundations():
    repos = [{"name": "a", "full_name": "u/a", "html_url": "https://g/a", "language": "Python", "topics": [], "pushed_at": None}]
    evidence = build_evidence(repos, {"u/a": {"FastAPI": "dependency", "PostgreSQL": "dependency"}})
    assert evidence["Git"][0]["signal"] == "repository"
    assert evidence["GitHub"][0]["signal"] == "repository"
    assert evidence["REST APIs"][0]["signal"] == "implied"
    assert evidence["SQL"][0]["signal"] == "implied"
    assert "JavaScript" not in evidence


def test_student_friendly_jobs_rank_above_senior_ones_with_better_scores():
    senior = job(1, ["Python", "Docker", "AWS"])
    senior.title = "Senior Engineer"
    entry = job(2, ["Python", "Java", "Rust"])
    results = job_matches([senior, entry], {"Python": 90, "Docker": 90, "AWS": 90})
    assert [r["id"] for r in results] == [2, 1]
