
import pandas as pd
import pytest

from app.services import excel_service


def test_append_reply_creates_and_appends_rows(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"

    monkeypatch.setattr(
        excel_service,
        "OUTPUT_FILE",
        output_file,
    )

    excel_service.append_reply(
        "P001",
        "I'm interested in a demo",
        "positive",
    )

    excel_service.append_reply(
        "P002",
        "Not interested",
        "negative",
    )

    result = pd.read_excel(output_file)

    assert len(result) == 2
    assert result.iloc[0]["prospect_id"] == "P001"
    assert result.iloc[1]["prospect_id"] == "P002"
    assert result.iloc[1]["sentiment"] == "negative"


def test_append_reply_skips_duplicates(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    assert excel_service.append_reply("P001", "Not interested", "negative") is True
    assert excel_service.append_reply("P001", "Not interested", "negative") is False
    # Same text from a different prospect is not a duplicate
    assert excel_service.append_reply("P002", "Not interested", "negative") is True

    result = pd.read_excel(output_file)
    assert len(result) == 2


def test_corrupted_file_raises_clear_error(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    output_file.write_text("not an excel file")
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    with pytest.raises(excel_service.ExcelFileCorruptedError):
        excel_service.append_reply("P001", "Hello", "positive")


def test_missing_columns_raises_clear_error(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    pd.DataFrame({"something_else": ["x"]}).to_excel(output_file, index=False)
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)

    with pytest.raises(excel_service.ExcelFileCorruptedError):
        excel_service.append_reply("P001", "Hello", "positive")


def test_locked_file_raises_clear_error_and_keeps_data(tmp_path, monkeypatch):
    output_file = tmp_path / "classified_replies.xlsx"
    monkeypatch.setattr(excel_service, "OUTPUT_FILE", output_file)
    excel_service.append_reply("P001", "Hello", "positive")

    def locked(*args, **kwargs):
        raise PermissionError("file is open in Excel")

    monkeypatch.setattr(excel_service.os, "replace", locked)

    with pytest.raises(excel_service.ExcelFileLockedError):
        excel_service.append_reply("P002", "Hi", "positive")

    # Original file is untouched and no temp file is left behind
    assert len(pd.read_excel(output_file)) == 1
    assert list(tmp_path.iterdir()) == [output_file]
