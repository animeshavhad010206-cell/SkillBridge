from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ReportIn
from ..services.github import GitHubError, cached_profile
from ..services.jobs import TARGET_ROLES
from ..services.report import build_report
from ..services.resume_parser import ResumeParseError, parse_resume

router = APIRouter(prefix="/api", tags=["resume"])

MAX_RESUME_BYTES = 5 * 1024 * 1024


def load_github(username: str | None) -> dict | None:
    cleaned = (username or "").strip().rstrip("/").rsplit("/", 1)[-1].lstrip("@")
    if not cleaned:
        return None
    try:
        return cached_profile(cleaned)
    except GitHubError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))


def check_role(target_role: str | None) -> str | None:
    if target_role and target_role not in TARGET_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a role from the list")
    return target_role or None


@router.get("/roles")
def target_roles():
    return list(TARGET_ROLES)


@router.post("/resume")
def parse_upload(
    file: UploadFile,
    github_username: str | None = Form(default=None, max_length=120),
    target_role: str | None = Form(default=None, max_length=60),
    db: Session = Depends(get_db),
):
    data = file.file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Resume must be 5 MB or smaller")
    try:
        _, parsed = parse_resume(file.filename, data)
    except ResumeParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    # The file is read in memory and never saved.
    resume = {"filename": (file.filename or "resume")[:255], **parsed}
    return build_report(db, resume, load_github(github_username), check_role(target_role))


@router.post("/report")
def update_report(body: ReportIn, db: Session = Depends(get_db)):
    role = check_role(body.target_role)
    return build_report(db, body.resume.model_dump(), load_github(body.github_username), role)
