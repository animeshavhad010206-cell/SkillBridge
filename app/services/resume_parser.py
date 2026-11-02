"""Turns a PDF or DOCX resume into structured data using text extraction and rules."""

import io
import re
from pathlib import PurePath

import pdfplumber
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.table import Table

from .skills import SKILLS, find_listed_skills, find_skills

MAX_PAGES = 10
MIN_TEXT_LENGTH = 50
MAX_LIST_ITEMS = 12

HEADINGS = {
    "summary": ["summary", "professional summary", "objective", "career objective", "profile", "about", "about me"],
    "skills": [
        "skills", "technical skills", "key skills", "core skills", "core competencies", "technologies",
        "tech stack", "technical proficiency", "technical expertise", "tools and technologies", "skills and tools",
    ],
    "experience": [
        "experience", "work experience", "professional experience", "employment", "employment history",
        "work history", "internship", "internships", "internship experience", "relevant experience",
    ],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "technical projects"],
    "education": ["education", "academics", "academic background", "academic qualifications", "qualifications"],
    "certifications": ["certifications", "certification", "certificates", "licenses", "courses", "coursework"],
    "other": [
        "achievements", "awards", "honors", "publications", "extracurricular", "extracurricular activities",
        "positions of responsibility", "leadership", "activities", "interests", "hobbies", "references",
    ],
}
SECTION_FOR_HEADING = {heading: section for section, headings in HEADINGS.items() for heading in headings}
INLINE_SKILL_LABEL = re.compile(
    r"^\s*(?:programming languages|languages|frameworks|libraries|tools|databases|technologies|"
    r"technical skills|skills|cloud|devops)\s*[:\-–]",
    re.I,
)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)\d{3,5}[\s.-]?\d{3,5}(?!\d)")
GITHUB = re.compile(r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))", re.I)
LINKEDIN = re.compile(r"linkedin\.com/in/[\w%-]+", re.I)


class ResumeParseError(ValueError):
    """The message is shown to the student, so it says how to fix the problem."""


def extract_pdf(data: bytes) -> tuple[str, list[str]]:
    pages, links = [], []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:MAX_PAGES]:
                pages.append(page.extract_text() or "")
                # Icon links on a resume are annotations, so they are missing from the text.
                links.extend(link["uri"] for link in page.hyperlinks if link.get("uri"))
    except Exception as exc:
        raise ResumeParseError("This PDF could not be read. It may be damaged or password protected.") from exc
    return "\n".join(pages), links


def extract_docx(data: bytes) -> tuple[str, list[str]]:
    try:
        document = Document(io.BytesIO(data))
        lines = []
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                for row in block.rows:
                    # Merged cells repeat, so keep each cell's text once.
                    lines.append(" | ".join(dict.fromkeys(c.text.strip() for c in row.cells if c.text.strip())))
            else:
                lines.append(block.text)
        links = [
            rel.target_ref
            for rel in document.part.rels.values()
            if rel.reltype == RELATIONSHIP_TYPE.HYPERLINK and rel.is_external
        ]
    except Exception as exc:
        raise ResumeParseError("This Word file could not be read. Try saving it again as .docx or PDF.") from exc
    return "\n".join(lines), links


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "header"
    for line in text.splitlines():
        heading = re.sub(r"[^a-z& ]", "", line.lower().replace("&", "and")).strip()
        heading = re.sub(r"\s+", " ", heading)
        if len(line) <= 45 and heading in SECTION_FOR_HEADING:
            current = SECTION_FOR_HEADING[heading]
            continue
        target = "skills" if INLINE_SKILL_LABEL.match(line) else current
        sections.setdefault(target, []).append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def find_name(lines: list[str]) -> str | None:
    for line in lines[:6]:
        candidate = line.strip()
        words = candidate.split()
        if not 2 <= len(words) <= 4 or re.search(r"[\d@/|:]", candidate):
            continue
        if candidate.lower() in SECTION_FOR_HEADING or find_skills(candidate):
            continue
        return candidate.title() if candidate.isupper() else candidate
    return None


def find_phone(text: str) -> str | None:
    for match in PHONE.finditer(text):
        if 10 <= len(re.sub(r"\D", "", match.group())) <= 13:
            return match.group().strip()
    return None


def find_github(text: str, links: list[str]) -> str | None:
    for source in [*links, text]:
        match = GITHUB.search(source)
        if match:
            return match.group(1)
    return None


def list_items(section: str) -> list[str]:
    items = [line.strip(" \t•·-–*") for line in section.splitlines()]
    return [item for item in items if item][:MAX_LIST_ITEMS]


def parse_text(text: str, links: list[str]) -> dict:
    sections = split_sections(text)
    lines = [line for line in text.splitlines() if line.strip()]
    contact_text = text[:1500]

    email = EMAIL.search(text)
    linkedin = next((m.group() for m in map(LINKEDIN.search, [*links, text]) if m), None)
    in_context = find_skills(f"{sections.get('experience', '')}\n{sections.get('projects', '')}")
    claimed = find_skills(text) | find_listed_skills(sections.get("skills", ""))

    return {
        "contact": {
            "name": find_name(lines),
            "email": email.group() if email else None,
            "phone": find_phone(contact_text),
            "github": find_github(text, links),
            "linkedin": linkedin,
        },
        "summary": sections.get("summary", ""),
        "education": list_items(sections.get("education", "")),
        "experience": list_items(sections.get("experience", "")),
        "projects": list_items(sections.get("projects", "")),
        "certifications": list_items(sections.get("certifications", "")),
        "skills": [
            {"name": name, "category": SKILLS[name].category, "in_context": name in in_context}
            for name in sorted(claimed)
        ],
    }


def parse_resume(filename: str, data: bytes) -> tuple[str, dict]:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix == ".pdf":
        text, links = extract_pdf(data)
    elif suffix == ".docx":
        text, links = extract_docx(data)
    else:
        raise ResumeParseError("Upload a PDF or .docx file.")

    text = text.replace("\x00", "").strip()
    if len(text) < MIN_TEXT_LENGTH:
        raise ResumeParseError(
            "No readable text was found. Scanned or image-only resumes are not supported, so export a text-based PDF."
        )
    return text, parse_text(text, links)
