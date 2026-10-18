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


def test_list_replies_returns_count_and_rows(monkeypatch):
    rows = [{"prospect_id": "P001", "reply_text": "Book a call", "sentiment": "positive"}]
    monkeypatch.setattr(replies, "read_replies", lambda **kwargs: rows)

    result = asyncio.run(replies.list_replies(sentiment=None, prospect_id=None, sort_by=None))

    assert result == {"count": 1, "replies": rows}


def test_list_replies_maps_storage_errors(monkeypatch):
    def fail(**kwargs):
        raise excel_service.ExcelFileCorruptedError("boom")

    monkeypatch.setattr(replies, "read_replies", fail)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(replies.list_replies(sentiment=None, prospect_id=None, sort_by=None))

    assert exc_info.value.status_code == 500


def test_create_reply_returns_scores(monkeypatch):
    saved = {}

    def fake_append(**kwargs):
        saved.update(kwargs)
        return True

    monkeypatch.setattr(replies, "append_reply", fake_append)

    result = post(reply_text="Book a call and sign me up")

    assert result["sentiment"] == "positive"
    assert result["positive_score"] == 6
    assert result["score_margin"] == 6
    assert result["opt_out"] is False
    assert saved["classification"].positive_score == 6


def test_priority_queue_endpoint(monkeypatch):
    calls = {}

    def fake_queue(**kwargs):
        calls.update(kwargs)
        return [{"rank": 1, "prospect_id": "P1",
                 "reply_text": "Book a call", "sentiment": "positive"}]

    monkeypatch.setattr(replies, "priority_queue", fake_queue)

    result = asyncio.run(replies.get_priority_queue(limit=10))

    assert result["count"] == 1
    assert calls == {"limit": 10}


def test_priority_queue_maps_storage_errors(monkeypatch):
    def fail(**kwargs):
        raise excel_service.ExcelFileLockedError("boom")

    monkeypatch.setattr(replies, "priority_queue", fail)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(replies.get_priority_queue(limit=50))

    assert exc_info.value.status_code == 503
