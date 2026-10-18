import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from app.schemas.reply import (
    PriorityList,
    ReplyCreated,
    ReplyList,
    ReplyRequest,
    Sentiment,
    SortField,
)
from app.services.classifier import score_reply
from app.services.priority import priority_queue
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


@router.get("", response_model=ReplyList)
async def list_replies(
    sentiment: Sentiment | None = Query(default=None, description="Only return replies with this sentiment"),
    prospect_id: str | None = Query(default=None, description="Only return replies from this prospect"),
    sort_by: SortField | None = Query(
        default=None,
        description="Sort highest first. Use score_margin with sentiment=positive to get the hottest leads first.",
    ),
):
    with storage_errors_as_http():
        replies = read_replies(sentiment=sentiment, prospect_id=prospect_id, sort_by=sort_by)

    return {"count": len(replies), "replies": replies}


@router.get("/priority", response_model=PriorityList)
async def get_priority_queue(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of replies to return"),
):
    """Positive replies ranked by score_margin, so a sales rep knows who to contact first."""
    with storage_errors_as_http():
        queue = priority_queue(limit=limit)

    return {"count": len(queue), "replies": queue}


@router.post("", status_code=201, response_model=ReplyCreated)
async def create_reply(reply: ReplyRequest):
    classification = score_reply(reply.reply_text)

    with storage_errors_as_http():
        saved = append_reply(
            prospect_id=reply.prospect_id,
            reply_text=reply.reply_text,
            classification=classification,
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
        **asdict(classification),
    }
