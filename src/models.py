from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UUID as SUUID
from sqlalchemy import DateTime
from sqlalchemy import Enum as SEnum
from sqlalchemy import Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FileStatus(str, Enum):
    UPLOADING = "upload"
    OK = "ok"
    ERROR = "error"
    BLOCKED = "blocked"


class FileMeta(Base):
    __tablename__ = "file_meta"

    id: Mapped[UUID] = mapped_column(SUUID(), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(SUUID(), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(length=255), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(
        String(length=255), nullable=True
    )
    status: Mapped[FileStatus] = mapped_column(SEnum(FileStatus), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
