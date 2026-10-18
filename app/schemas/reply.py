from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "negative", "neutral"]
SortField = Literal["positive_score", "negative_score", "neutral_score", "score_margin"]


class ReplyRequest(BaseModel):
    # Strip surrounding spaces so whitespace-only values fail min_length
    model_config = ConfigDict(str_strip_whitespace=True)

    prospect_id: str = Field(min_length=1, max_length=100)
    reply_text: str = Field(min_length=1, max_length=5000)


class ReplyRecord(BaseModel):
    prospect_id: str
    reply_text: str
    sentiment: str
    # None for replies saved before scores were recorded
    positive_score: float | None = None
    negative_score: float | None = None
    neutral_score: float | None = None
    score_margin: float | None = None
    opt_out: bool | None = None


class ReplyCreated(ReplyRecord):
    message: str


class ReplyList(BaseModel):
    count: int
    replies: list[ReplyRecord]


class PriorityItem(ReplyRecord):
    rank: int


class PriorityList(BaseModel):
    count: int
    replies: list[PriorityItem]
