import asyncio

import pytest
from fastapi import HTTPException

from app.routers import replies
from app.schemas.reply import ReplyRequest
from app.services import excel_service


def post(prospect_id="P001", reply_text="I'm interested"):
    return asyncio.run(
        replies.create_reply(ReplyRequest(prospect_id=prospect_id, reply_text=reply_text))
    )


@pytest.mark.parametrize(
    "error, status",
    [
        (excel_service.ExcelFileLockedError, 503),
        (excel_service.ExcelFileCorruptedError, 500),
        (excel_service.ExcelStorageError, 500),
    ],
)
def test_storage_errors_map_to_http_errors(monkeypatch, error, status):
    def fail(**kwargs):
        raise error("boom")

    monkeypatch.setattr(replies, "append_reply", fail)

    with pytest.raises(HTTPException) as exc_info:
        post()

    assert exc_info.value.status_code == status
    assert "boom" not in exc_info.value.detail  # internal details are not exposed


def test_duplicate_returns_409(monkeypatch):
    monkeypatch.setattr(replies, "append_reply", lambda **kwargs: False)

    with pytest.raises(HTTPException) as exc_info:
        post()

    assert exc_info.value.status_code == 409


def test_whitespace_only_input_is_rejected():
    with pytest.raises(ValueError):
        ReplyRequest(prospect_id="   ", reply_text="Hello")
