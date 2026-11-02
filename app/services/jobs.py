"""Live job postings from the Himalayas public API.

Himalayas' API terms require us to use their application link, credit them with a visible
link, cache responses, and remove jobs once they expire. Keep all four when changing this file.
"""

import html
import json
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import utcnow
from ..models import Job
from .skills import SKILLS, find_skills

SEARCH_URL = "https://himalayas.app/jobs/api/search"
SOURCE_URL = "https://himalayas.app"
SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_jobs.json"
TIMEOUT = 10
PAGES_PER_ROLE = 3
RETRY_AFTER = timedelta(minutes=10)
MIN_DEMAND_COUNT = 2
TOP_DEMAND_SKILLS = 20

TARGET_ROLES = {
    "Frontend Developer": {
        "query": "frontend developer",
        "titles": ["front end", "front-end", "frontend", "react", "angular", "vue", "ui developer", "ui engineer"],
    },
    "Backend Developer": {
        "query": "backend developer",
        "titles": ["back end", "back-end", "backend", "java developer", "python developer", "node", "api developer"],
    },
    "Full Stack Developer": {
        "query": "full stack developer",
        "titles": ["full stack", "full-stack", "fullstack", "mern", "software engineer", "software developer"],
    },
    "Data Analyst": {"query": "data analyst", "titles": ["analyst", "analytics", "business intelligence", "bi developer"]},
    "Data Scientist": {"query": "data scientist", "titles": ["data scien", "machine learning", "ai scientist"]},
    "Machine Learning Engineer": {
        "query": "machine learning engineer",
        "titles": ["machine learning", "ml engineer", "ai engineer", "mlops", "deep learning", "nlp", "llm"],
    },
    "DevOps Engineer": {
        "query": "devops engineer",
        "titles": ["devops", "site reliability", "sre", "cloud engineer", "platform engineer", "infrastructure"],
    },
    "Mobile Developer": {
        "query": "mobile developer",
        "titles": ["mobile", "android", "ios", "flutter", "react native"],
    },
}

_lock = threading.Lock()
_last_attempt: dict[str, datetime] = {}


class JobFeedError(Exception):
    pass


def strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value or ""))


def _from_epoch(value) -> datetime | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None)


def parse_posting(raw: dict, role: str) -> dict | None:
    title = html.unescape(raw.get("title") or "").strip()
    apply_url = raw.get("applicationLink")
    guid = raw.get("guid") or apply_url
    lowered = title.lower()
    if not title or not apply_url or not guid:
        return None
    if not any(word in lowered for word in TARGET_ROLES[role]["titles"]):
        return None  # Search matches the description too, so check the title really is this role.

    return {
        "guid": guid[:500],
        "role": role,
        "title": title[:300],
        "company": (raw.get("companyName") or "Unknown company")[:200],
        "apply_url": apply_url[:1000],
        "source_url": guid[:1000] if guid.startswith("http") else SOURCE_URL,
        "location": ", ".join(str(l) for l in (raw.get("locationRestrictions") or [])[:3])[:300],
        "seniority": ", ".join(str(s) for s in (raw.get("seniority") or []))[:100],
        "skills": sorted(find_skills(f"{title}\n{strip_html(raw.get('description') or '')}")),
        "source": "himalayas",
        "published_at": _from_epoch(raw.get("pubDate")),
        "expires_at": _from_epoch(raw.get("expiryDate")),
    }


def fetch_role_jobs(role: str) -> list[dict]:
    query = TARGET_ROLES[role]["query"]
    postings: dict[str, dict] = {}
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": "SkillBridge"}) as client:
        for page in range(1, PAGES_PER_ROLE + 1):
            try:
                response = client.get(
                    SEARCH_URL,
                    params={"q": query, "country": settings.job_country, "sort": "recent", "page": page},
                )
                response.raise_for_status()
                jobs = response.json().get("jobs") or []
            except (httpx.HTTPError, ValueError) as exc:
                if postings:
                    break  # Keep what the earlier pages returned.
                raise JobFeedError(str(exc)) from exc
            if not jobs:
                break
            for raw in jobs:
                posting = parse_posting(raw, role)
                if posting:
                    postings[posting["guid"]] = posting
    return list(postings.values())


def _store_samples(db: Session, role: str) -> None:
    samples = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))[role]
    for number, skills in enumerate(samples, start=1):
        db.add(
            Job(
                guid=f"sample-{role}-{number}",
                role=role,
                title=f"Sample {role} posting {number}",
                company="Sample data",
                skills=skills,
                source="sample",
            )
        )


def ensure_role_jobs(db: Session, role: str, force: bool = False) -> None:
    """Keep a role's jobs fresh. A failed feed keeps old data, then falls back to labelled samples."""
    now = utcnow()
    with _lock:
        db.execute(delete(Job).where(Job.expires_at.is_not(None), Job.expires_at < now))

        fetched = db.scalar(select(func.max(Job.fetched_at)).where(Job.role == role, Job.source == "himalayas"))
        fresh = fetched is not None and now - fetched < timedelta(hours=settings.job_refresh_hours)
        attempted = _last_attempt.get(role)
        recently_failed = attempted is not None and now - attempted < RETRY_AFTER

        if force or not (fresh or recently_failed):
            _last_attempt[role] = now
            try:
                postings = fetch_role_jobs(role)
            except JobFeedError:
                postings = []
            if postings:
                db.execute(delete(Job).where(Job.role == role))
                db.add_all(Job(**posting) for posting in postings)
                db.commit()
                return

        if not db.scalar(select(func.count()).select_from(Job).where(Job.role == role)):
            _store_samples(db, role)
        db.commit()


def jobs_for_role(db: Session, role: str) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.role == role).order_by(Job.published_at.desc())))


def market_demand(jobs: list[Job]) -> dict:
    counts = Counter(skill for job in jobs for skill in job.skills if skill in SKILLS)
    total = len(jobs)
    skills = [
        {"name": name, "category": SKILLS[name].category, "count": count, "share": round(100 * count / total)}
        for name, count in counts.most_common(TOP_DEMAND_SKILLS)
        if count >= MIN_DEMAND_COUNT
    ]
    return {
        "total_jobs": total,
        "source": "sample" if jobs and all(j.source == "sample" for j in jobs) else "himalayas",
        "source_url": SOURCE_URL,
        "fetched_at": max((j.fetched_at for j in jobs), default=None),
        "skills": skills,
    }
