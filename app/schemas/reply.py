from pydantic import BaseModel, ConfigDict, Field


class ReplyRequest(BaseModel):
    # Strip surrounding spaces so whitespace-only values fail min_length
    model_config = ConfigDict(str_strip_whitespace=True)

    prospect_id: str = Field(min_length=1, max_length=100)
    reply_text: str = Field(min_length=1, max_length=5000)
