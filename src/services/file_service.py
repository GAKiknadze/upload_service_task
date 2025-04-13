from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from io import TextIOWrapper
from mimetypes import guess_extension, guess_type, add_type
from typing import AsyncGenerator, List, Tuple
from uuid import UUID

from fsspec import AbstractFileSystem  # type:ignore[import-untyped]
from fsspec.spec import AbstractBufferedFile  # type:ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import (
    BadFileFormatExc,
    FileNotFoundExc,
    FileTooBigExc,
    InitServiceExc,
)
from ..models import FileMeta, FileStatus
from ..utils import singleton


class AbstractAsyncIO(ABC):
    @abstractmethod
    async def write(self, data: bytes) -> None:
        pass

    @abstractmethod
    async def read(self, size: int = -1) -> bytes:
        pass

    @abstractmethod
    async def seek(self, offset: int) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


@singleton
class FileService:
    _storage: AbstractFileSystem

    _max_file_size: int = 10

    _supported_formats: List[str] = ["*"]

    def set_storage(self, value: AbstractFileSystem) -> None:
        if self._storage is not None:
            raise InitServiceExc("File storage is already set")
        self._storage = value

    def set_max_file_size(self, value: int) -> None:
        self._max_file_size = value

    def set_supported_formats(self, value: List[str | Tuple[str, str]]) -> None:
        """
        Example:
            value = ["text/text", ("application/custom", ".custom_format")]
        """
        formats = list()
        for v in value:
            if isinstance(v, Tuple[str, str]):
                doc_type, doc_ext = v
                saved_type, _ = guess_type(doc_ext)
                if saved_type is None:
                    add_type(doc_type, doc_ext)
                    formats.append(doc_type)
            else:
                formats.append(v)
        self._supported_formats = formats

    @staticmethod
    def _get_uuid_file_name(file_id: UUID, mime_type: str | None = None) -> str:
        if not mime_type:
            return str(file_id)

        if mime_type == "application/octet-stream":
            extension = ".bin"
        else:
            extension = guess_extension(mime_type) or ""
        return f"{file_id}{extension}"

    async def upload(
        self,
        session: AsyncSession,
        file: AbstractAsyncIO,
        name: str,
        user_id: UUID | None = None,
        size: int | None = None,
        content_type: str | None = None,
    ) -> FileMeta:
        if content_type is None and name is not None:
            content_type, _ = guess_type(name)

        if (
            "*" not in self._supported_formats
            and content_type is not None
            and content_type not in self._supported_formats
        ):
            raise BadFileFormatExc(
                f"File format must be one of: {self._supported_formats}"
            )

        if size is not None and size > self._max_file_size:
            raise FileTooBigExc(f"Max file size `{self._max_file_size}`")

        file_meta = FileMeta(
            owner_id=user_id,
            name=name,
            size=size,
            content_type=content_type,
            status=FileStatus.UPLOADING,
        )
        await session.add(file_meta)
        await session.commit()

        internal_file_name = self._get_uuid_file_name(
            file_meta.id, file_meta.content_type
        )

        try:
            async with self._storage.open(internal_file_name, "wb") as f:
                f.write(await file.read())
        except Exception:
            file_meta.status = FileStatus.ERROR
        else:
            file_meta.status = FileStatus.OK
            file_meta.internal_name = internal_file_name
        await session.flush([file_meta])
        await session.commit()
        return file_meta

    @asynccontextmanager
    async def get_file(
        self, session: AsyncSession, file_id: UUID
    ) -> AsyncGenerator[TextIOWrapper | AbstractBufferedFile, None]:
        file_meta = await self.get_info(session, file_id)
        if file_meta.status in (
            FileStatus.UPLOADING,
            FileStatus.ERROR,
            FileStatus.BLOCKED,
        ):
            raise FileNotFoundExc(f"File with id `{file_id}`")
        async with self._storage.open(file_meta.internal_name, "rb") as f:
            yield f

    async def get_info(self, session: AsyncSession, file_id: UUID) -> FileMeta:
        file_meta = await session.get(FileMeta, file_id)
        if file_meta is None:
            raise FileNotFoundExc(f"File with id `{file_id}`")
        return file_meta

    async def delete(self, session: AsyncSession, file_id: UUID) -> None:
        file_meta = await self.get_info(session, file_id)
        await self._storage.rm(file_meta.internal_name)
        await session.delete(file_meta)
