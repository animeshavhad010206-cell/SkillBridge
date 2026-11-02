"""Builds the full result for one resume. Nothing about the person is stored."""

from sqlalchemy.orm import Session

from .jobs import TARGET_ROLES, ensure_role_jobs, jobs_for_role, market_demand
from .matching import job_matches, readiness, skill_gaps
from .trust import build_skills, identity_signals


def status_counts(skills: list[dict]) -> dict:
    counts = {"verified": 0, "partial": 0, "unverified": 0}
    for skill in skills:
        counts[skill["status"]] += 1
    return counts


def github_out(github: dict | None) -> dict | None:
    if not github:
        return None
    return {key: value for key, value in github.items() if key != "evidence"}


def build_report(db: Session, resume: dict, github: dict | None, target_role: str | None) -> dict:
    skills = build_skills(resume["skills"], github["evidence"] if github else {})
    trust = {skill["name"]: skill["trust_score"] for skill in skills}
    report = {
        "resume": resume,
        "github": github_out(github),
        "identity": identity_signals(resume["contact"], github),
        "target_role": target_role,
        "skills": skills,
        "status_counts": status_counts(skills),
        "market": None,
        "scores": None,
        "gaps": None,
        "jobs": [],
    }
    if target_role in TARGET_ROLES:
        ensure_role_jobs(db, target_role)
        jobs = jobs_for_role(db, target_role)
        demand = market_demand(jobs)
        report["market"] = demand
        report["scores"] = readiness(trust, demand["skills"])
        report["gaps"] = skill_gaps(trust, demand["skills"])
        report["jobs"] = job_matches(jobs, trust)
    return report
