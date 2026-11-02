import io
import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tempfile.mkdtemp()) / 'test.db').as_posix()}"

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import main
from app.database import Base, engine
from app.services import jobs


@pytest.fixture(autouse=True)
def offline_jobs(monkeypatch):
    """Tests never call the real feed, so jobs come from the sample file."""

    def fail(role):
        raise jobs.JobFeedError("offline")

    monkeypatch.setattr(jobs, "fetch_role_jobs", fail)
    jobs._last_attempt.clear()


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(main.app) as test_client:
        yield test_client


def make_docx(lines: list[str]) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page text PDF, written by hand to avoid a test-only dependency."""

    def escape(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(f"({escape(line)}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n{body}\nendobj\n"
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    output += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    output += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return output.encode("latin-1")


RESUME_LINES = [
    "Priya Sharma",
    "priya.sharma@example.com | +91 98765 43210",
    "github.com/priyasharma | linkedin.com/in/priya-sharma",
    "Education",
    "B.Tech Computer Engineering, 2021 - 2025",
    "Technical Skills",
    "Languages: Python, JavaScript, Go, C++",
    "Frameworks: React, FastAPI",
    "Tools: Docker, Postgre",
    "Projects",
    "Campus Connect - built a dashboard with React and a Python backend",
    "Experience",
    "Software Intern, Acme Corp",
    "Wrote REST APIs and deployed with Docker",
]
