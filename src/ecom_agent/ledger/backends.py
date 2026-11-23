"""Storage backends for the ledger.

CsvLedger   - a folder of CSV files, one per tab. Used for the demo and tests.
SheetsLedger - a Google Sheet, one worksheet per tab, via a service account.

Pick one with the LEDGER_BACKEND environment variable (see .env.example).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Protocol

from .schema import TABS, coerce, validate


class Ledger(Protocol):
    def read(self, tab: str) -> list[dict]: ...
    def append(self, tab: str, row: dict) -> None: ...
    def update(self, tab: str, key_col: str, key: str, changes: dict) -> bool: ...


class CsvLedger:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def _path(self, tab: str) -> Path:
        if tab not in TABS:
            raise ValueError(f"unknown tab {tab!r}")
        return self.folder / f"{tab.lower()}.csv"

    def read(self, tab: str) -> list[dict]:
        path = self._path(tab)
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            return [coerce(r) for r in csv.DictReader(f)]

    def append(self, tab: str, row: dict) -> None:
        problems = validate(tab, row)
        if problems:
            raise ValueError("; ".join(problems))
        path = self._path(tab)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TABS[tab])
            if new:
                w.writeheader()
            w.writerow(row)

    def update(self, tab: str, key_col: str, key: str, changes: dict) -> bool:
        rows = self.read(tab)
        hit = False
        for r in rows:
            if r.get(key_col) == key:
                r.update(changes)
                hit = True
        if hit:
            with self._path(tab).open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=TABS[tab])
                w.writeheader()
                w.writerows(rows)
        return hit


class SheetsLedger:
    """Google Sheets backend. Share the sheet with the service account's
    email (Editor) and set GOOGLE_SHEET_ID and GOOGLE_APPLICATION_CREDENTIALS."""

    def __init__(self, sheet_id: str, credentials_file: str):
        import gspread  # imported lazily so the demo runs without it

        self._book = gspread.service_account(filename=credentials_file).open_by_key(sheet_id)

    def _ws(self, tab: str):
        if tab not in TABS:
            raise ValueError(f"unknown tab {tab!r}")
        return self._book.worksheet(tab)

    def read(self, tab: str) -> list[dict]:
        return [coerce(r) for r in self._ws(tab).get_all_records()]

    def append(self, tab: str, row: dict) -> None:
        problems = validate(tab, row)
        if problems:
            raise ValueError("; ".join(problems))
        self._ws(tab).append_row([row[c] for c in TABS[tab]], value_input_option="USER_ENTERED")

    def update(self, tab: str, key_col: str, key: str, changes: dict) -> bool:
        ws = self._ws(tab)
        cols = TABS[tab]
        cell = ws.find(key, in_column=cols.index(key_col) + 1)
        if cell is None:
            return False
        for col, val in changes.items():
            ws.update_cell(cell.row, cols.index(col) + 1, val)
        return True


def ledger_from_env() -> Ledger:
    backend = os.getenv("LEDGER_BACKEND", "csv").lower()
    if backend == "sheets":
        return SheetsLedger(os.environ["GOOGLE_SHEET_ID"], os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    default = Path(__file__).resolve().parents[3] / "data" / "sample"
    return CsvLedger(os.getenv("LEDGER_CSV_DIR", str(default)))
