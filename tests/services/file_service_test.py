from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fsspec.spec import AbstractBufferedFile

from src.exceptions import (
    BadFileFormatExc,
    FileNotFoundExc,
    FileTooBigExc,
    InitServiceExc,
)
from src.models import FileMeta, FileStatus
from src.services.file_service import FileService


def test_set_storage_twice():
    service = FileService()
    service.set_storage(MagicMock())

    with pytest.raises(InitServiceExc):
        service.set_storage(MagicMock())


@pytest.mark.asyncio
async def test_upload_success(mocker):
    mock_session = AsyncMock()
    mock_file = MagicMock()
    mock_file.read = AsyncMock(return_value=b"data")

    service = FileService()
    service.set_storage(MagicMock())
    service.set_max_file_size(10)
    service.set_supported_formats(["*"])

    result = await service.upload(
        session=mock_session,
        file=mock_file,
        name="test.txt",
        user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        size=4,
        content_type="text/plain",
    )

    assert result.status == FileStatus.OK
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upload_bad_format():
    service = FileService()
    service.set_supported_formats(["image/png"])

    with pytest.raises(BadFileFormatExc):
        await service.upload(
            session=AsyncMock(),
            file=MagicMock(),
            name="test.jpg",
            content_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_upload_file_too_big():
    service = FileService()
    service.set_max_file_size(5)
    service.set_supported_formats(["*"])

    with pytest.raises(FileTooBigExc):
        await service.upload(
            session=AsyncMock(), file=MagicMock(), name="test.bin", size=10
        )


@pytest.mark.asyncio
async def test_get_file_success(mocker):
    service = FileService()

    mock_storage = mocker.MagicMock()

    mock_file = AsyncMock()
    mock_file.__aenter__ = AsyncMock(
        return_value=mocker.MagicMock(spec=AbstractBufferedFile)
    )
    mock_file.__aexit__ = AsyncMock(return_value=None)

    mock_storage.open.return_value = mock_file
    service.set_storage(mock_storage)

    mock_session = mocker.AsyncMock()
    file_meta = FileMeta(
        status=FileStatus.OK,
        content_type="text/plain",
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    )
    mock_session.get.return_value = file_meta

    async with service.get_file(mock_session, file_meta.id) as f:
        assert f is not None

    mock_storage.open.assert_called_once_with(
        service._get_uuid_file_name(file_meta.id, file_meta.content_type), "rb"
    )


@pytest.mark.asyncio
async def test_get_file_invalid_status():
    mock_session = AsyncMock()
    file_meta = FileMeta(status=FileStatus.UPLOADING)
    mock_session.get.return_value = file_meta

    service = FileService()

    with pytest.raises(FileNotFoundExc):
        async with service.get_file(
            mock_session, UUID("123e4567-e89b-12d3-a456-426614174000")
        ):
            pass


@pytest.mark.asyncio
async def test_delete(mocker):
    mock_session = AsyncMock()
    mock_storage = MagicMock()
    mock_storage.rm = AsyncMock()

    service = FileService()
    service.set_storage(mock_storage)

    file_meta = FileMeta(id=UUID("123e4567-e89b-12d3-a456-426614174000"))
    mock_session.get.return_value = file_meta

    await service.delete(mock_session, file_meta.id)

    mock_storage.rm.assert_awaited()
    mock_session.delete.assert_called_once_with(file_meta)


@pytest.mark.asyncio
async def test_upload_storage_error(mocker):
    mock_storage = MagicMock()
    mock_storage.open.side_effect = Exception("Storage error")

    service = FileService()
    service.set_storage(mock_storage)

    result = await service.upload(
        session=AsyncMock(), file=MagicMock(), name="test.txt"
    )

    assert result.status == FileStatus.ERROR
