import logging

from fastapi import APIRouter, HTTPException

from app.schemas.reply import ReplyRequest
from app.services.classifier import classify_reply
from app.services.excel_service import (
    ExcelFileCorruptedError,
    ExcelFileLockedError,
    ExcelStorageError,
    append_reply,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replies", tags=["Replies"])


@router.post("/", status_code=201)
async def create_reply(reply: ReplyRequest):
    sentiment = classify_reply(reply.reply_text)

    try:
        saved = append_reply(
            prospect_id=reply.prospect_id,
            reply_text=reply.reply_text,
            sentiment=sentiment,
        )
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
        logger.exception("Failed to save reply to Excel")
        raise HTTPException(
            status_code=500,
            detail="The reply could not be saved due to a storage error.",
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
