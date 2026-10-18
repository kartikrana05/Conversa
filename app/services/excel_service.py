import os
from dataclasses import asdict
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

from app.services.classifier import ClassificationResult

OUTPUT_FILE = Path("output/classified_replies.xlsx")

# Every file must have these; they identify and describe the reply
TEXT_COLUMNS = ["prospect_id", "reply_text", "sentiment"]
# Added later: files saved before scoring existed don't have them, and their rows are left blank
SCORE_COLUMNS = ["positive_score", "negative_score", "neutral_score", "score_margin"]
FLAG_COLUMNS = ["opt_out"]
COLUMNS = TEXT_COLUMNS + SCORE_COLUMNS + FLAG_COLUMNS

SORTABLE_COLUMNS = SCORE_COLUMNS


class ExcelStorageError(Exception):
    """Base error for problems reading or writing the replies Excel file."""


class ExcelFileLockedError(ExcelStorageError):
    """The file is open in another program (e.g. Excel) or not writable."""


class ExcelFileCorruptedError(ExcelStorageError):
    """The file exists but is not a valid replies workbook."""


def _read_existing() -> pd.DataFrame:
    try:
        existing = pd.read_excel(OUTPUT_FILE, dtype={col: str for col in TEXT_COLUMNS})
    except PermissionError as exc:
        raise ExcelFileLockedError(f"Cannot read {OUTPUT_FILE}") from exc
    except (BadZipFile, InvalidFileException, ValueError) as exc:
        raise ExcelFileCorruptedError(f"{OUTPUT_FILE} is not a valid Excel file") from exc
    except OSError as exc:
        raise ExcelStorageError(f"Cannot read {OUTPUT_FILE}") from exc

    missing = set(TEXT_COLUMNS) - set(existing.columns)
    if missing:
        raise ExcelFileCorruptedError(
            f"{OUTPUT_FILE} is missing columns: {', '.join(sorted(missing))}"
        )

    # Older files have no score columns; anything that isn't a number becomes blank
    for col in SCORE_COLUMNS:
        existing[col] = pd.to_numeric(existing.get(col), errors="coerce")
    existing["opt_out"] = existing.get("opt_out", pd.Series(index=existing.index)).map(
        {True: True, False: False}
    )
    return existing[COLUMNS]


def _write(df: pd.DataFrame) -> None:
    # Write to a temp file and swap it in, so a failed write never corrupts the real file
    tmp_file = OUTPUT_FILE.with_name(OUTPUT_FILE.stem + ".tmp.xlsx")
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(tmp_file, index=False)
        os.replace(tmp_file, OUTPUT_FILE)
    except PermissionError as exc:
        raise ExcelFileLockedError(f"Cannot write {OUTPUT_FILE}") from exc
    except OSError as exc:
        raise ExcelStorageError(f"Cannot write {OUTPUT_FILE}") from exc
    finally:
        tmp_file.unlink(missing_ok=True)


def read_replies(
    sentiment: str | None = None,
    prospect_id: str | None = None,
    sort_by: str | None = None,
) -> list[dict]:
    """Return saved replies, optionally filtered and sorted (highest first).

    Returns [] if nothing has been saved yet. Rows saved before scoring existed
    have None for the score fields and are listed last when sorting.
    """
    if not OUTPUT_FILE.exists():
        return []

    df = _read_existing()
    df[TEXT_COLUMNS] = df[TEXT_COLUMNS].fillna("")
    if sentiment is not None:
        df = df[df["sentiment"] == sentiment]
    if prospect_id is not None:
        df = df[df["prospect_id"] == prospect_id]
    if sort_by is not None:
        if sort_by not in SORTABLE_COLUMNS:
            raise ValueError(f"Cannot sort by {sort_by!r}")
        df = df.sort_values(sort_by, ascending=False, na_position="last", kind="stable")

    # Blank cells become None so they serialise as JSON null
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


def append_reply(
    prospect_id: str,
    reply_text: str,
    classification: ClassificationResult,
) -> bool:
    """Append a reply row. Returns False if the same prospect already sent this exact reply."""
    new_row = pd.DataFrame(
        [{"prospect_id": prospect_id, "reply_text": reply_text, **asdict(classification)}],
        columns=COLUMNS,
    )

    if OUTPUT_FILE.exists():
        existing = _read_existing()
        is_duplicate = (
            (existing["prospect_id"] == prospect_id)
            & (existing["reply_text"] == reply_text)
        ).any()
        if is_duplicate:
            return False
        df = pd.concat([existing, new_row], ignore_index=True)
    else:
        df = new_row

    _write(df)
    return True
