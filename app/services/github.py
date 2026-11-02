"""Reads public GitHub activity and works out which skills each repository shows evidence of."""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from ..config import settings
from .skills import lookup_skill

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
TIMEOUT = 10
DEEP_SCAN_REPOS = 8
MIN_LANGUAGE_SHARE = 0.05
CACHE_SECONDS = 3600
MAX_CACHED_PROFILES = 500
MANIFESTS = ("package.json", "requirements.txt", "Dockerfile")
RAW_CONNECT_TIMEOUT = 3
RAW_RETRY_SECONDS = 600

_cache: dict[str, tuple[float, dict]] = {}
_raw_retry_at = 0.0

USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][\w.-]*)")

# GitHub's language names that differ from the skill dictionary.
LANGUAGE_NAMES = {
    "Jupyter Notebook": "Python",
    "Shell": "Bash",
    "Dockerfile": "Docker",
    "HCL": "Terraform",
    "SCSS": "Sass",
}


# A repository that uses a skill on the right also shows the skill on the left.
IMPLIED_SKILLS = {
    "REST APIs": {"FastAPI", "Flask", "Django", "Express", "Spring Boot"},
    "SQL": {"PostgreSQL", "MySQL", "SQLite"},
    "JavaScript": {"React", "Next.js", "Vue", "Angular", "Svelte", "Node.js", "Express", "TypeScript"},
}


class GitHubError(Exception):
    """The message is shown to the student."""


def _client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SkillBridge"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return httpx.Client(headers=headers, timeout=TIMEOUT, follow_redirects=True)


def _get_json(client: httpx.Client, path: str, params: dict | None = None):
    try:
        response = client.get(f"{API}{path}", params=params)
    except httpx.HTTPError as exc:
        raise GitHubError("GitHub could not be reached. Try again in a moment.") from exc
    if response.status_code == 404:
        raise GitHubError("No GitHub account was found with that username.")
    if response.status_code in (403, 429):
        raise GitHubError("GitHub's hourly limit was reached. Try again later, or add a GITHUB_TOKEN on the server.")
    if response.status_code != 200:
        raise GitHubError("GitHub returned an unexpected response. Try again in a moment.")
    return response.json()


def _read_raw(client: httpx.Client, repo: dict) -> dict[str, str] | None:
    """raw.githubusercontent.com does not count against the API limit, but some networks block it."""
    global _raw_retry_at
    if time.monotonic() < _raw_retry_at:
        return None
    found = {}
    for name in MANIFESTS:
        try:
            response = client.get(
                f"{RAW}/{repo['full_name']}/{repo['default_branch']}/{name}",
                timeout=httpx.Timeout(TIMEOUT, connect=RAW_CONNECT_TIMEOUT),
            )
        except httpx.TransportError:
            _raw_retry_at = time.monotonic() + RAW_RETRY_SECONDS
            return None
        if response.status_code == 200:
            found[name] = response.text
    return found


def _read_via_api(client: httpx.Client, repo: dict) -> dict[str, str]:
    """Lists the repository first so that files it does not have cost no API calls."""
    try:
        listing = _get_json(client, f"/repos/{repo['full_name']}/contents")
    except GitHubError:
        return {}
    present = {item["name"] for item in listing if item.get("type") == "file"}

    found = {}
    for name in MANIFESTS:
        if name not in present:
            continue
        try:
            response = client.get(
                f"{API}/repos/{repo['full_name']}/contents/{name}",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
        except httpx.HTTPError:
            continue
        if response.status_code == 200:
            found[name] = response.text
    return found


def _read_manifests(client: httpx.Client, repo: dict) -> dict[str, str]:
    raw = _read_raw(client, repo)
    return raw if raw is not None else _read_via_api(client, repo)


def skills_from_package_json(text: str) -> set[str]:
    try:
        manifest = json.loads(text)
    except ValueError:
        return set()
    if not isinstance(manifest, dict):
        return set()
    names: list[str] = []
    for key in ("dependencies", "devDependencies"):
        section = manifest.get(key)
        if isinstance(section, dict):
            names.extend(section)
    return {skill for skill in map(lookup_skill, names) if skill}


def skills_from_requirements(text: str) -> set[str]:
    names = (m.group(1) for m in map(REQUIREMENT_NAME.match, text.splitlines()) if m)
    return {skill for skill in map(lookup_skill, names) if skill}


def _scan_repo(client: httpx.Client, repo: dict) -> dict[str, str]:
    """Deep scan of one repository. Returns skill -> how it was detected."""
    found: dict[str, str] = {}
    try:
        languages = _get_json(client, f"/repos/{repo['full_name']}/languages")
    except GitHubError:
        languages = {}
    total = sum(languages.values())
    for language, size in languages.items():
        if total and size / total >= MIN_LANGUAGE_SHARE:
            skill = lookup_skill(LANGUAGE_NAMES.get(language, language))
            if skill:
                found[skill] = "language"

    manifests = _read_manifests(client, repo)
    if "package.json" in manifests:
        found.update(dict.fromkeys(skills_from_package_json(manifests["package.json"]), "dependency"))
    if "requirements.txt" in manifests:
        found.update(dict.fromkeys(skills_from_requirements(manifests["requirements.txt"]), "dependency"))
    if "Dockerfile" in manifests:
        found["Docker"] = "dependency"
    return found


def build_evidence(repos: list[dict], deep_scans: dict[str, dict[str, str]]) -> dict[str, list[dict]]:
    evidence: dict[str, list[dict]] = {}
    for repo in repos:
        detected = dict(deep_scans.get(repo["full_name"], {}))
        primary = repo.get("language")
        if primary:
            skill = lookup_skill(LANGUAGE_NAMES.get(primary, primary))
            if skill:
                detected.setdefault(skill, "language")
        for topic in repo.get("topics") or []:
            skill = lookup_skill(topic)
            if skill:
                detected.setdefault(skill, "topic")
        for skill, sources in IMPLIED_SKILLS.items():
            if sources & detected.keys():
                detected.setdefault(skill, "implied")
        # Every repository here was pushed with Git to GitHub.
        detected.setdefault("Git", "repository")
        detected.setdefault("GitHub", "repository")
        for skill, signal in detected.items():
            evidence.setdefault(skill, []).append(
                {"repo": repo["name"], "url": repo["html_url"], "pushed_at": repo.get("pushed_at"), "signal": signal}
            )
    return evidence


def fetch_profile(username: str) -> dict:
    if not USERNAME.match(username):
        raise GitHubError("That does not look like a valid GitHub username.")

    with _client() as client:
        profile = _get_json(client, f"/users/{username}")
        repos = _get_json(client, f"/users/{username}/repos", {"per_page": 100, "type": "owner", "sort": "pushed"})
        repos = [r for r in repos if not r.get("fork") and r.get("size", 0) > 0]

        scanned = repos[:DEEP_SCAN_REPOS]
        with ThreadPoolExecutor(max_workers=4) as pool:
            scans = list(pool.map(lambda repo: _scan_repo(client, repo), scanned))

    return {
        "login": profile["login"],
        "name": profile.get("name"),
        "avatar_url": profile.get("avatar_url"),
        "html_url": profile.get("html_url"),
        "created_at": profile.get("created_at"),
        "public_repos": len(repos),
        "followers": profile.get("followers", 0),
        "scanned_repos": len(scanned),
        "evidence": build_evidence(repos, {r["full_name"]: s for r, s in zip(scanned, scans)}),
    }


def cached_profile(username: str) -> dict:
    """GitHub's limit is low, so a report that changes only the target role must not spend calls."""
    key = username.lower()
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and now - cached[0] < CACHE_SECONDS:
        return cached[1]
    profile = fetch_profile(username)
    if len(_cache) >= MAX_CACHED_PROFILES:
        _cache.clear()
    _cache[key] = (now, profile)
    return profile


def parse_github_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
