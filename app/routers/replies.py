import logging
from collections.abc import Generator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Query

from app.schemas.reply import ReplyList, ReplyRequest, Sentiment
from app.services.classifier import classify_reply
from app.services.excel_service import (
    ExcelFileCorruptedError,
    ExcelFileLockedError,
    ExcelStorageError,
    append_reply,
    read_replies,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replies", tags=["Replies"])


@contextmanager
def storage_errors_as_http() -> Generator[None]:
    """Turn Excel storage failures into clear HTTP errors without leaking internals."""
    try:
        yield
    except ExcelFileLockedError:
        logger.exception("Replies Excel file is locked")
        raise HTTPException(
            status_code=503,
            detail="The replies file is open in another program. Close it and try again.",
            headers={"Retry-After": "10"},
        )
    except ExcelFileCorruptedError:
        logger.exception("Replies Excel file is corrupted")
        raise HTTPException(
            status_code=500,
            detail="The replies file is damaged or has the wrong format. Fix or remove it and try again.",
        )
    except ExcelStorageError:
        logger.exception("Replies Excel storage error")
        raise HTTPException(
            status_code=500,
            detail="The replies file could not be accessed due to a storage error.",
        )


@router.get("/", response_model=ReplyList)
async def list_replies(
    sentiment: Sentiment | None = Query(default=None, description="Only return replies with this sentiment"),
    prospect_id: str | None = Query(default=None, description="Only return replies from this prospect"),
):
    with storage_errors_as_http():
        replies = read_replies(sentiment=sentiment, prospect_id=prospect_id)

    return {"count": len(replies), "replies": replies}


@router.post("/", status_code=201)
async def create_reply(reply: ReplyRequest):
    sentiment = classify_reply(reply.reply_text)

    with storage_errors_as_http():
        saved = append_reply(
            prospect_id=reply.prospect_id,
            reply_text=reply.reply_text,
            sentiment=sentiment,
        )

    if not saved:
        raise HTTPException(
            status_code=409,
            detail="This reply from this prospect has already been saved",
        )

    return {
        "message": "Reply classified and saved successfully",
        "prospect_id": reply.prospect_id,
        "reply_text": reply.reply_text,
        "sentiment": sentiment,
    }
