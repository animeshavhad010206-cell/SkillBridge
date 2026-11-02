from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect as inspect_db

from app import main, models
from app.database import SessionLocal, engine
from app.routers import parser
from app.services import github, jobs

from .conftest import RESUME_LINES, make_docx, make_pdf

GITHUB_DATA = {
    "login": "priyasharma",
    "name": "Priya Sharma",
    "public_repos": 2,
    "scanned_repos": 2,
    "evidence": {
        "React": [{"repo": "app", "url": "https://github.com/p/app", "pushed_at": "2026-09-01T00:00:00Z", "signal": "dependency"}],
        "Python": [{"repo": "api", "url": "https://github.com/p/api", "pushed_at": "2026-09-01T00:00:00Z", "signal": "language"}],
    },
}


def upload(client, name="resume.docx", data=None, **form):
    files = {"file": (name, data if data is not None else make_docx(RESUME_LINES))}
    return client.post("/api/resume", files=files, data=form)


def skills_of(report):
    return {skill["name"]: skill for skill in report["skills"]}


def test_page_routes_serve_the_frontend_but_api_paths_stay_404(tmp_path):
    (tmp_path / "index.html").write_text("<title>SkillBridge</title>")
    app = FastAPI()
    app.mount("/", main.SinglePageApp(directory=tmp_path, html=True))
    site = TestClient(app)

    assert "SkillBridge" in site.get("/anything").text
    assert site.get("/api/missing").status_code == 404


def test_resume_parses_without_an_account(client):
    response = upload(client)
    assert response.status_code == 200
    report = response.json()
    assert report["resume"]["filename"] == "resume.docx"
    assert report["resume"]["contact"]["github"] == "priyasharma"
    assert skills_of(report)["React"]["status"] == "partial"
    assert report["market"] is None


def test_upload_parses_pdf_too(client):
    assert upload(client, "resume.pdf", make_pdf(RESUME_LINES)).json()["resume"]["contact"]["name"] == "Priya Sharma"


def test_nothing_about_the_person_is_stored(client):
    upload(client, target_role="Backend Developer")
    assert inspect_db(engine).get_table_names() == ["jobs"]


def test_upload_rejects_bad_files(client):
    assert upload(client, "resume.txt", b"hello").status_code == 422
    assert upload(client, "resume.pdf", b"not a pdf").status_code == 422
    assert upload(client, "resume.pdf", b"x" * (5 * 1024 * 1024 + 1)).status_code == 413


def test_github_and_role_refine_the_report(client, monkeypatch):
    monkeypatch.setattr(parser, "cached_profile", lambda username: GITHUB_DATA)
    resume = upload(client).json()["resume"]

    report = client.post("/api/report", json={"resume": resume, "github_username": "https://github.com/priyasharma/"}).json()
    assert skills_of(report)["React"]["status"] == "verified"
    assert skills_of(report)["Go"]["status"] == "unverified"
    assert report["identity"] == {"resume_links_account": True, "name_matches": True}
    assert "evidence" not in report["github"]

    report = client.post("/api/report", json={"resume": resume, "target_role": "Full Stack Developer"}).json()
    assert report["github"] is None
    assert report["market"]["source"] == "sample"
    assert report["scores"]["readiness"] <= report["scores"]["coverage"]
    assert report["jobs"]
    assert report["gaps"]["missing"][0]["resources"]


def test_replacing_a_resume_keeps_github_and_role(client, monkeypatch):
    monkeypatch.setattr(parser, "cached_profile", lambda username: GITHUB_DATA)
    report = upload(client, github_username="priyasharma", target_role="Backend Developer").json()
    assert report["github"]["login"] == "priyasharma"
    assert report["target_role"] == "Backend Developer"


def test_rejects_unknown_role(client):
    assert upload(client, target_role="Astronaut").status_code == 422
    resume = upload(client).json()["resume"]
    assert client.post("/api/report", json={"resume": resume, "target_role": "Astronaut"}).status_code == 422


def test_skills_outside_the_dictionary_are_ignored(client):
    resume = upload(client).json()["resume"]
    resume["skills"].append({"name": "Time Travel", "in_context": True})
    assert "Time Travel" not in skills_of(client.post("/api/report", json={"resume": resume}).json())


def test_github_failure_is_reported(client, monkeypatch):
    def fail(username):
        raise parser.GitHubError("No GitHub account was found with that username.")

    monkeypatch.setattr(parser, "cached_profile", fail)
    resume = upload(client).json()["resume"]
    response = client.post("/api/report", json={"resume": resume, "github_username": "missing"})
    assert response.status_code == 502
    assert "No GitHub account" in response.json()["detail"]


def test_github_profiles_are_cached_and_failures_are_not(monkeypatch):
    calls = []

    def fetch(username):
        calls.append(username)
        if username == "bad":
            raise github.GitHubError("nope")
        return GITHUB_DATA

    monkeypatch.setattr(github, "fetch_profile", fetch)
    github._cache.clear()
    github.cached_profile("PriyaSharma")
    github.cached_profile("priyasharma")
    assert calls == ["PriyaSharma"]

    for _ in range(2):
        try:
            github.cached_profile("bad")
        except github.GitHubError:
            pass
    assert calls.count("bad") == 2


def test_no_account_routes_exist(client):
    assert set(main.app.openapi()["paths"]) == {"/api/health", "/api/roles", "/api/resume", "/api/report"}


def test_live_jobs_replace_samples_and_expired_jobs_are_removed(client, monkeypatch):
    resume = upload(client).json()["resume"]
    body = {"resume": resume, "target_role": "Mobile Developer"}
    assert client.post("/api/report", json=body).json()["market"]["source"] == "sample"

    live = {
        "guid": "live-1", "role": "Mobile Developer", "title": "Flutter Developer", "company": "Acme",
        "apply_url": "https://himalayas.app/apply/1", "source_url": "https://himalayas.app/jobs/1", "location": "India",
        "seniority": "Entry-level", "skills": ["Flutter", "Dart", "Git"], "source": "himalayas",
        "published_at": None, "expires_at": None,
    }
    monkeypatch.setattr(jobs, "fetch_role_jobs", lambda role: [live])
    jobs._last_attempt.clear()
    with SessionLocal() as db:
        jobs.ensure_role_jobs(db, "Mobile Developer")
        job = db.query(models.Job).one()
        assert job.source == "himalayas"
        job.expires_at = jobs.utcnow() - jobs.timedelta(days=1)
        job.fetched_at = jobs.utcnow()
        db.commit()
        jobs.ensure_role_jobs(db, "Mobile Developer")
        assert db.query(models.Job).filter_by(guid="live-1").count() == 0
