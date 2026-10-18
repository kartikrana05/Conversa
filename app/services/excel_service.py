import os
from pathlib import Path
from zipfile import BadZipFile

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException

OUTPUT_FILE = Path("output/classified_replies.xlsx")

COLUMNS = ["prospect_id", "reply_text", "sentiment"]


class ExcelStorageError(Exception):
    """Base error for problems reading or writing the replies Excel file."""


class ExcelFileLockedError(ExcelStorageError):
    """The file is open in another program (e.g. Excel) or not writable."""


class ExcelFileCorruptedError(ExcelStorageError):
    """The file exists but is not a valid replies workbook."""


def _read_existing() -> pd.DataFrame:
    try:
        existing = pd.read_excel(OUTPUT_FILE, dtype=str)
    except PermissionError as exc:
        raise ExcelFileLockedError(f"Cannot read {OUTPUT_FILE}") from exc
    except (BadZipFile, InvalidFileException, ValueError) as exc:
        raise ExcelFileCorruptedError(f"{OUTPUT_FILE} is not a valid Excel file") from exc
    except OSError as exc:
        raise ExcelStorageError(f"Cannot read {OUTPUT_FILE}") from exc

    missing = set(COLUMNS) - set(existing.columns)
    if missing:
        raise ExcelFileCorruptedError(
            f"{OUTPUT_FILE} is missing columns: {', '.join(sorted(missing))}"
        )
    return existing


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


def append_reply(prospect_id: str, reply_text: str, sentiment: str) -> bool:
    """Append a reply row. Returns False if the same prospect already sent this exact reply."""
    new_row = pd.DataFrame(
        [[prospect_id, reply_text, sentiment]],
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
