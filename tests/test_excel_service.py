import pandas as pd
import pytest

from app.services import excel_service
from app.services.classifier import score_reply


def save(prospect_id, reply_text):
    return excel_service.append_reply(prospect_id, reply_text, score_reply(reply_text))


def test_append_reply_creates_and_appends_rows(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"

    monkeypatch.setattr(
        excel_service,
        "OUTPUT_FILE",
        output_file,
    )

    save("P001", "I'm interested in a demo")
    save("P002", "Not interested")

    result = pd.read_excel(output_file)

    assert len(result) == 2
    assert result.iloc[0]["prospect_id"] == "P001"
    assert result.iloc[1]["prospect_id"] == "P002"
    assert result.iloc[1]["sentiment"] == "negative"


def test_append_reply_skips_duplicates(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    assert save("P001", "Not interested") is True
    assert save("P001", "Not interested") is False
    # Same text from a different prospect is not a duplicate
    assert save("P002", "Not interested") is True

    result = pd.read_excel(output_file)
    assert len(result) == 2


def test_corrupted_file_raises_clear_error(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    output_file.write_text("not an excel file")
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    with pytest.raises(excel_service.ExcelFileCorruptedError):
        save("P001", "Hello")


def test_missing_columns_raises_clear_error(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    pd.DataFrame({"something_else": ["x"]}).to_excel(output_file, index=False)
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    with pytest.raises(excel_service.ExcelFileCorruptedError):
        save("P001", "Hello")


def test_locked_file_raises_clear_error_and_keeps_data(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)
    save("P001", "Hello")

    def locked(*args, **kwargs):
        raise PermissionError("file is open in Excel")

    monkeypatch.setattr(excel_service.os, "replace", locked)

    with pytest.raises(excel_service.ExcelFileLockedError):
        save("P002", "Hi")

    # Original file is untouched and no temp file is left behind
    assert len(pd.read_excel(output_file)) == 1
    assert list(tmp_path.iterdir()) == [output_file]


def test_read_replies_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", tmp_path / "missing.xlsx")

    assert excel_service.read_replies() == []


def test_read_replies_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", tmp_path / "classified_replies.xlsx")
    save("P001", "Book a call")
    save("P002", "Not interested")
    save("P001", "Tell me more")

    assert len(excel_service.read_replies()) == 3
    assert [r["prospect_id"] for r in excel_service.read_replies(sentiment="negative")] == ["P002"]
    assert [r["reply_text"] for r in excel_service.read_replies(prospect_id="P001")] == [
        "Book a call",
        "Tell me more",
    ]
    assert excel_service.read_replies(sentiment="negative", prospect_id="P001") == []


def test_scores_are_saved(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)
    save("P001", "Book a call and sign me up")

    row = pd.read_excel(output_file).iloc[0]
    assert row["sentiment"] == "positive"
    assert row["positive_score"] == 6
    assert row["negative_score"] == 0
    assert row["score_margin"] == 6
    assert bool(row["opt_out"]) is False

    [reply] = excel_service.read_replies()
    assert reply["positive_score"] == 6
    assert reply["opt_out"] is False


def test_old_file_without_score_columns_still_works(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    pd.DataFrame(
        [["P001", "Not interested", "negative"]],
        columns=["prospect_id", "reply_text", "sentiment"],
    ).to_excel(output_file, index=False)
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    [old] = excel_service.read_replies()
    assert old["sentiment"] == "negative"
    assert old["positive_score"] is None
    assert old["opt_out"] is None

    assert save("P002", "Book a call") is True

    result = pd.read_excel(output_file)
    assert list(result.columns) == excel_service.COLUMNS
    assert len(result) == 2
    assert pd.isna(result.iloc[0]["positive_score"])
    assert result.iloc[1]["positive_score"] == 3


def test_read_replies_sorts_highest_first_with_blanks_last(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    pd.DataFrame(
        [["P000", "Old reply", "positive"]],
        columns=["prospect_id", "reply_text", "sentiment"],
    ).to_excel(output_file, index=False)
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)
    save("P001", "Sure")
    save("P002", "Book a call and sign me up")
    save("P003", "Tell me more")

    ranked = excel_service.read_replies(sentiment="positive", sort_by="score_margin")

    assert [r["prospect_id"] for r in ranked] == ["P002", "P003", "P001", "P000"]
