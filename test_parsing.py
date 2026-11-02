import json
import re
from pathlib import Path

import pytest

from app.services.jobs import parse_posting, strip_html
from app.services.resume_parser import ResumeParseError, parse_resume, split_sections
from app.services.skills import SKILLS, find_listed_skills, find_skills

from .conftest import RESUME_LINES, make_docx, make_pdf


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We use Java and SQL", {"Java", "SQL"}),
        ("JavaScript developer", {"JavaScript"}),
        ("MySQL and NoSQL stores", {"MySQL", "NoSQL"}),
        ("Skilled in C++, C# and .NET", {"C++", "C#", ".NET"}),
        ("Node.js with Express.js", {"Node.js", "Express"}),
        ("Python-based services on AWS.", {"Python", "AWS"}),
        ("HTML/CSS/JS", {"HTML", "CSS", "JavaScript"}),
        ("Languages: Python, Go, R", {"Python", "Go", "R"}),
        ("Built with React Native", {"React Native"}),
        ("React and React Native", {"React", "React Native"}),
    ],
)
def test_finds_skills(text, expected):
    assert find_skills(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Go to the market and get things done",
        "We trust our team to excel at swift delivery in the spring",
        "R&D lead at a C-level consultancy",
        "An express delivery service",
        "Graduated with honors, a keen reader",
        "See https://example.com/python/react for more",
        "Write to react@example.com",
    ],
)
def test_ignores_ordinary_english_and_links(text):
    assert find_skills(text) == set()


def test_fuzzy_matching_catches_typos_only_in_skill_lists():
    assert "PostgreSQL" in find_listed_skills("Postgre, Javascrpt")
    assert "JavaScript" in find_listed_skills("Postgre, Javascrpt")
    assert find_listed_skills("Teamwork, Leadership, Communication") == set()


def test_splits_sections_and_keeps_inline_skill_labels():
    sections = split_sections("EDUCATION\nBTech\nPROJECTS:\nA chat app\nTools: Docker\nMore project text")
    assert sections["education"] == "BTech"
    assert "A chat app" in sections["projects"]
    assert "More project text" in sections["projects"]
    assert "Tools: Docker" in sections["skills"]


@pytest.mark.parametrize(
    ("filename", "data"),
    [("resume.docx", make_docx(RESUME_LINES)), ("resume.pdf", make_pdf(RESUME_LINES))],
)
def test_parses_a_full_resume(filename, data):
    _, parsed = parse_resume(filename, data)
    contact = parsed["contact"]
    assert contact["name"] == "Priya Sharma"
    assert contact["email"] == "priya.sharma@example.com"
    assert contact["phone"] == "+91 98765 43210"
    assert contact["github"] == "priyasharma"
    assert contact["linkedin"] == "linkedin.com/in/priya-sharma"
    assert "B.Tech Computer Engineering, 2021 - 2025" in parsed["education"]

    skills = {s["name"]: s for s in parsed["skills"]}
    assert {"Python", "JavaScript", "Go", "C++", "React", "FastAPI", "Docker", "PostgreSQL", "REST APIs"} <= set(skills)
    assert skills["React"]["in_context"] is True  # Used in a project
    assert skills["Docker"]["in_context"] is True  # Used in the internship
    assert skills["JavaScript"]["in_context"] is False  # Only listed


@pytest.mark.parametrize(
    ("filename", "data"),
    [
        ("resume.txt", b"plain text"),
        ("resume.pdf", b"this is not a pdf"),
        ("resume.docx", b"this is not a docx"),
        ("scan.pdf", make_pdf(["too short"])),
    ],
)
def test_rejects_unreadable_files(filename, data):
    with pytest.raises(ResumeParseError):
        parse_resume(filename, data)


def test_every_skill_in_samples_exists_in_the_dictionary():
    samples = json.loads((Path(__file__).parent.parent / "app" / "data" / "sample_jobs.json").read_text("utf-8"))
    assert {s for postings in samples.values() for posting in postings for s in posting} <= set(SKILLS)


def test_parse_posting_extracts_skills_and_uses_the_application_link():
    posting = parse_posting(
        {
            "title": "Senior React Developer",
            "companyName": "Acme",
            "description": "<p>You know <b>React</b> &amp; TypeScript.</p>",
            "applicationLink": "https://himalayas.app/apply/1",
            "guid": "https://himalayas.app/jobs/1",
            "seniority": ["Senior"],
            "locationRestrictions": ["India"],
            "pubDate": 1793536892,
            "expiryDate": 1796128892,
        },
        "Frontend Developer",
    )
    assert posting["apply_url"] == "https://himalayas.app/apply/1"
    assert posting["skills"] == ["React", "TypeScript"]
    assert posting["location"] == "India"


def test_parse_posting_drops_jobs_from_other_professions():
    raw = {"title": "Recruiter for React teams", "applicationLink": "https://x.test/a", "guid": "a"}
    assert parse_posting(dict(raw, title="Account Manager"), "Frontend Developer") is None


def test_strip_html_leaves_no_tags():
    assert not re.search(r"<[^>]+>", strip_html("<h2>Role</h2><ul><li>Python</li></ul>"))
