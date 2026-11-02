"""Skill-gap and job-match scoring. Scores use trust, so an unproven claim counts for less than a verified one."""

from ..models import Job
from .skills import SKILLS, resources_for
from .trust import PARTIAL_AT, VERIFIED_AT

REQUIRED_SKILLS = 15
MIN_JOB_SKILLS = 3
TOP_JOB_MATCHES = 10
TOP_GAPS = 8
SENIOR_WORDS = ("senior", "sr.", "lead", "staff", "principal", "manager", "director", "head of")


def readiness(trust: dict[str, int], demand: list[dict]) -> dict:
    """Both scores weight each skill by market demand.

    coverage takes the student's claims at face value. readiness discounts them by trust.
    The distance between the two is how much of the profile is unproven.
    """
    required = demand[:REQUIRED_SKILLS]
    total = sum(item["share"] for item in required)
    if not total:
        return {"readiness": 0, "coverage": 0}
    proven = sum(item["share"] * trust.get(item["name"], 0) / 100 for item in required)
    claimed = sum(item["share"] for item in required if item["name"] in trust)
    return {"readiness": round(100 * proven / total), "coverage": round(100 * claimed / total)}


def skill_gaps(trust: dict[str, int], demand: list[dict]) -> dict:
    required = demand[:REQUIRED_SKILLS]
    missing = [
        {**item, "resources": resources_for(item["name"])} for item in required if item["name"] not in trust
    ][:TOP_GAPS]
    weak = [
        {**item, "trust_score": trust[item["name"]], "resources": resources_for(item["name"])}
        for item in required
        if item["name"] in trust and trust[item["name"]] < VERIFIED_AT
    ][:TOP_GAPS]
    return {"missing": missing, "weak": weak}


def match_job(job: Job, trust: dict[str, int]) -> dict:
    matched = [s for s in job.skills if trust.get(s, 0) >= PARTIAL_AT]
    unproven = [s for s in job.skills if 0 < trust.get(s, 0) < PARTIAL_AT]
    missing = [s for s in job.skills if s not in trust]
    score = round(sum(trust.get(s, 0) for s in job.skills) / len(job.skills))
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "seniority": job.seniority,
        "apply_url": job.apply_url,
        "source": job.source,
        "source_url": job.source_url,
        "published_at": job.published_at,
        "match_score": score,
        "matched": matched,
        "unproven": unproven,
        "missing": missing,
    }


def is_senior(result: dict) -> bool:
    text = f"{result['title']} {result['seniority']}".lower()
    return any(word in text for word in SENIOR_WORDS)


def job_matches(jobs: list[Job], trust: dict[str, int]) -> list[dict]:
    usable = [job for job in jobs if sum(s in SKILLS for s in job.skills) >= MIN_JOB_SKILLS]
    results = [match_job(job, trust) for job in usable]
    # SkillBridge users are students, so roles open to them rank above senior ones.
    return sorted(results, key=lambda r: (is_senior(r), -r["match_score"]))[:TOP_JOB_MATCHES]
