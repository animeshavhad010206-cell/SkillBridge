from datetime import datetime

from sqlalchemy import JSON, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, utcnow


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("role", "guid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str] = mapped_column(String(300), default="")
    seniority: Mapped[str] = mapped_column(String(100), default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="himalayas")
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
