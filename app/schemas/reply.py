from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "negative", "neutral"]


class ReplyRequest(BaseModel):
    # Strip surrounding spaces so whitespace-only values fail min_length
    model_config = ConfigDict(str_strip_whitespace=True)

    prospect_id: str = Field(min_length=1, max_length=100)
    reply_text: str = Field(min_length=1, max_length=5000)


class ReplyRecord(BaseModel):
    prospect_id: str
    reply_text: str
    sentiment: str


class ReplyList(BaseModel):
    count: int
    replies: list[ReplyRecord]
