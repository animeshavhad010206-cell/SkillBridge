"""Combines the resume and GitHub into one trust score per skill."""

from datetime import timedelta

from rapidfuzz import fuzz

from ..database import utcnow
from .github import parse_github_time
from .skills import SKILLS

RESUME_CLAIM = 30
USED_IN_PROJECT_OR_JOB = 15
PER_REPO = 10
MAX_REPOS_COUNTED = 3
RECENT_ACTIVITY = 25
RECENT_DAYS = 365

VERIFIED_AT = 70
PARTIAL_AT = 45
NAME_MATCH_RATIO = 75
MAX_EVIDENCE_SHOWN = 5


def score_skill(on_resume: bool, in_context: bool, repo_count: int, recently_active: bool) -> int:
    score = 0
    if on_resume:
        score += RESUME_CLAIM
    if in_context:
        score += USED_IN_PROJECT_OR_JOB
    score += min(repo_count, MAX_REPOS_COUNTED) * PER_REPO
    if repo_count and recently_active:
        score += RECENT_ACTIVITY
    return score


def status_for(score: int) -> str:
    if score >= VERIFIED_AT:
        return "verified"
    return "partial" if score >= PARTIAL_AT else "unverified"


def build_skills(resume_skills: list[dict], evidence: dict[str, list[dict]]) -> list[dict]:
    claimed = {skill["name"]: skill for skill in resume_skills}
    cutoff = utcnow() - timedelta(days=RECENT_DAYS)

    skills = []
    for name in set(claimed) | set(evidence):
        if name not in SKILLS:
            continue  # Resume data comes back from the browser, so only dictionary skills count.
        repos = evidence.get(name, [])
        pushes = [t for t in (parse_github_time(r.get("pushed_at")) for r in repos) if t]
        last_active = max(pushes, default=None)
        on_resume = name in claimed
        in_context = on_resume and claimed[name]["in_context"]
        score = score_skill(on_resume, in_context, len(repos), bool(last_active and last_active >= cutoff))
        skills.append(
            {
                "name": name,
                "category": SKILLS[name].category,
                "on_resume": on_resume,
                "in_context": in_context,
                "repo_count": len(repos),
                "evidence": repos[:MAX_EVIDENCE_SHOWN],
                "last_active": last_active,
                "trust_score": score,
                "status": status_for(score),
            }
        )
    return sorted(skills, key=lambda s: (-s["trust_score"], s["name"]))


def identity_signals(contact: dict, github: dict | None) -> dict:
    """Hints that the GitHub account is the student's own. GitHub cannot prove this."""
    if not github:
        return {"resume_links_account": None, "name_matches": None}

    linked = contact.get("github")
    resume_name = contact.get("name")
    github_name = github.get("name")
    return {
        "resume_links_account": linked.lower() == github["login"].lower() if linked else None,
        "name_matches": fuzz.token_set_ratio(resume_name.lower(), github_name.lower()) >= NAME_MATCH_RATIO
        if resume_name and github_name
        else None,
    }
