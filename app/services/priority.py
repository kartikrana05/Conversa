"""Builds the sales rep's priority queue from saved replies.

Only positive replies are included, clearest first (highest score_margin).
Replies saved before scores existed have no score_margin and go last.
"""

from app.services.excel_service import read_replies


def priority_queue(limit: int | None = None) -> list[dict]:
    queue = read_replies(sentiment="positive", sort_by="score_margin")

    if limit is not None:
        queue = queue[:limit]

    return [{"rank": rank, **reply} for rank, reply in enumerate(queue, start=1)]
