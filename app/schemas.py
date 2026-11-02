from pydantic import BaseModel, Field


class ResumeSkill(BaseModel):
    name: str = Field(max_length=60)
    category: str = Field(default="", max_length=40)
    in_context: bool = False


class ResumeContact(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    github: str | None = Field(default=None, max_length=120)
    linkedin: str | None = Field(default=None, max_length=300)


class ParsedResume(BaseModel):
    """The server keeps no resumes, so the browser sends the parsed result back to change the report."""

    filename: str = Field(default="resume", max_length=255)
    contact: ResumeContact = ResumeContact()
    summary: str = Field(default="", max_length=5000)
    education: list[str] = Field(default=[], max_length=50)
    experience: list[str] = Field(default=[], max_length=50)
    projects: list[str] = Field(default=[], max_length=50)
    certifications: list[str] = Field(default=[], max_length=50)
    skills: list[ResumeSkill] = Field(default=[], max_length=300)


class ReportIn(BaseModel):
    resume: ParsedResume
    github_username: str | None = Field(default=None, max_length=120)
    target_role: str | None = Field(default=None, max_length=60)
