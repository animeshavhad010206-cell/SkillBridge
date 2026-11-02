"""Skill dictionary and matching. Everything here is deterministic: regex, plus fuzzy matching for typos."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz, process

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "skills.json"

BEFORE = r"(?<![\w+#.-])"
AFTER = r"(?![\w+#])(?!\.\w)"
LIST_LEFT = r"(?:^|[,|/:;•·()\n]|\band\b|\bor\b)[ \t]*"
LIST_RIGHT = r"[ \t]*(?:$|[,|/;•·()\n.]|\band\b|\bor\b)"
URLS_AND_EMAILS = re.compile(r"https?://\S+|www\.\S+|\S+@\S+|\S+\.(?:com|org|io|dev|in)/\S*", re.I)

FUZZY_CUTOFF = 88
FUZZY_MIN_LENGTH = 5

CATEGORY_ROADMAPS = {
    "Languages": ("Developer roadmaps", "https://roadmap.sh/"),
    "Frontend": ("Frontend roadmap", "https://roadmap.sh/frontend"),
    "Backend": ("Backend roadmap", "https://roadmap.sh/backend"),
    "Databases": ("SQL roadmap", "https://roadmap.sh/sql"),
    "DevOps & Cloud": ("DevOps roadmap", "https://roadmap.sh/devops"),
    "Data & ML": ("AI and data scientist roadmap", "https://roadmap.sh/ai-data-scientist"),
    "Mobile": ("Android roadmap", "https://roadmap.sh/android"),
    "Testing": ("QA roadmap", "https://roadmap.sh/qa"),
    "Tools": ("Git and GitHub roadmap", "https://roadmap.sh/git-github"),
    "Practices": ("Software design roadmap", "https://roadmap.sh/software-design-architecture"),
}


@dataclass
class Skill:
    name: str
    category: str
    resources: list[dict]
    patterns: list[re.Pattern] = field(default_factory=list)


def _load() -> tuple[dict[str, Skill], dict[str, str], dict[str, str]]:
    skills, aliases, lookup = {}, {}, {}
    for entry in json.loads(DATA_FILE.read_text(encoding="utf-8")):
        name = entry["name"]
        words = [a.lower() for a in entry.get("aliases", [])]
        if not entry.get("strict"):
            words.append(name.lower())

        patterns = []
        if words:
            joined = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
            blocked = entry.get("not_followed_by")
            exclusion = f"(?![ -]{blocked})" if blocked else ""
            patterns.append(re.compile(f"{BEFORE}(?:{joined}){AFTER}{exclusion}", re.I))
        for word in entry.get("list_only", []):
            # Words like "Go" and "R" are too common to match in prose, so they only count in a list.
            patterns.append(re.compile(f"{LIST_LEFT}{re.escape(word)}{LIST_RIGHT}", re.M))

        skills[name] = Skill(
            name=name,
            category=entry["category"],
            resources=[{"title": t, "url": u} for t, u in entry.get("resources", [])],
            patterns=patterns,
        )
        for word in words:
            aliases[word] = name
        for word in [*words, *entry.get("packages", [])]:
            lookup[word.lower()] = name
        lookup[name.lower()] = name
    return skills, aliases, lookup


SKILLS, _ALIASES, _LOOKUP = _load()
_FUZZY_CHOICES = [alias for alias in _ALIASES if len(alias) >= FUZZY_MIN_LENGTH]


def find_skills(text: str) -> set[str]:
    cleaned = URLS_AND_EMAILS.sub(" ", text)
    return {skill.name for skill in SKILLS.values() if any(p.search(cleaned) for p in skill.patterns)}


def find_listed_skills(text: str) -> set[str]:
    """find_skills plus typo-tolerant matching. Only safe on a skills section, where every item is a skill."""
    found = find_skills(text)
    for item in re.split(r"[,|;•·:/\n()]+", text):
        term = item.strip().lower()
        if not FUZZY_MIN_LENGTH <= len(term) <= 30 or len(term.split()) > 3:
            continue
        match = process.extractOne(term, _FUZZY_CHOICES, scorer=fuzz.ratio, score_cutoff=FUZZY_CUTOFF)
        if match:
            found.add(_ALIASES[match[0]])
    return found


def lookup_skill(name: str) -> str | None:
    """Exact lookup for a package, GitHub language or repo topic."""
    return _LOOKUP.get(name.strip().lower())


def resources_for(skill_name: str) -> list[dict]:
    skill = SKILLS[skill_name]
    title, url = CATEGORY_ROADMAPS[skill.category]
    return [*skill.resources, {"title": title, "url": url}]
