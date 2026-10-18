import pandas as pd

from app.services import excel_service, priority
from app.services.classifier import score_reply


def save(prospect_id, reply_text):
    return excel_service.append_reply(prospect_id, reply_text, score_reply(reply_text))


def use_temp_file(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)
    return output_file


def test_empty_when_nothing_saved(tmp_path, monkeypatch):
    use_temp_file(tmp_path, monkeypatch)

    assert priority.priority_queue() == []


def test_positive_replies_ranked_by_score_margin(tmp_path, monkeypatch):
    use_temp_file(tmp_path, monkeypatch)
    save("P1", "Sure")
    save("P2", "Book a call and sign me up")
    save("P3", "Tell me more")

    queue = priority.priority_queue()

    assert [r["prospect_id"] for r in queue] == ["P2", "P3", "P1"]
    assert [r["rank"] for r in queue] == [1, 2, 3]


def test_only_positive_replies_are_included(tmp_path, monkeypatch):
    use_temp_file(tmp_path, monkeypatch)
    save("P1", "Book a call")
    save("P2", "No thanks, not interested")
    save("P3", "I am interested, but please unsubscribe me")  # opt-out
    save("P4", "Maybe next quarter, circle back later")  # neutral

    queue = priority.priority_queue()

    assert [r["prospect_id"] for r in queue] == ["P1"]


def test_limit(tmp_path, monkeypatch):
    use_temp_file(tmp_path, monkeypatch)
    save("P1", "Sure")
    save("P2", "Book a call and sign me up")
    save("P3", "Tell me more")

    queue = priority.priority_queue(limit=2)

    assert [r["prospect_id"] for r in queue] == ["P2", "P3"]


def test_old_rows_without_scores_go_last(tmp_path, monkeypatch):
    output_file = use_temp_file(tmp_path, monkeypatch)
    pd.DataFrame(
        [["P0", "Old positive reply", "positive"]],
        columns=["prospect_id", "reply_text", "sentiment"],
    ).to_excel(output_file, index=False)
    save("P1", "Sure")

    queue = priority.priority_queue()

    assert [r["prospect_id"] for r in queue] == ["P1", "P0"]
    assert queue[1]["score_margin"] is None
