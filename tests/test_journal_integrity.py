"""journal.jsonl must stay machine-readable.

Six records were structurally broken between 2026-07-19 and 2026-08-08, by the
bulk "Import CorbeauSplat v2 (Studio)" commit — not by the journal-writing
code. Each had lost an array key and its opening bracket, leaving the elements
as bare strings inside the object. Nothing crashed, because the file is read
line by line, so the damage sat unnoticed for six weeks.

These tests are cheap and would have caught it the same day.
"""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

JOURNAL = Path(__file__).resolve().parent.parent / "journal.jsonl"


def _records():
    return [
        (num, line)
        for num, line in enumerate(JOURNAL.read_text(encoding="utf-8").splitlines(), 1)
        if line.strip()
    ]


@pytest.fixture(scope="module")
def records():
    if not JOURNAL.exists():
        pytest.skip("journal.jsonl absent")
    return _records()


def test_every_line_is_valid_json(records):
    broken = []
    for num, line in records:
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            broken.append(f"line {num}: {e}")
    assert broken == [], "malformed records:\n" + "\n".join(broken)


def test_no_duplicate_keys_in_a_record(records):
    """json.loads keeps the last duplicate and drops the earlier one silently.

    A repair that reuses a key already present in the record would therefore
    look successful while discarding exactly the content it recovered.
    """
    offenders = []
    for num, line in records:
        keys = re.findall(r'"([a-z_]+)":', line)
        dupes = [k for k, c in Counter(keys).items() if c > 1]
        if dupes:
            offenders.append(f"line {num}: {dupes}")
    assert offenders == [], "duplicate keys:\n" + "\n".join(offenders)


def test_mandatory_fields_are_present(records):
    """date, session and lot identify a record; without them it is unusable."""
    missing = [
        f"line {num}: {[k for k in ('date', 'session', 'lot') if k not in json.loads(line)]}"
        for num, line in records
        if not all(k in json.loads(line) for k in ("date", "session", "lot"))
    ]
    assert missing == [], "records missing identifying fields:\n" + "\n".join(missing)


def test_dates_are_iso_and_ordered(records):
    dates = [json.loads(line)["date"] for _, line in records]
    malformed = [d for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d))]
    assert malformed == [], f"non-ISO dates: {malformed}"
    assert dates == sorted(dates), "records are not in chronological order"
