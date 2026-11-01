"""Shared timestamp parsing for offline CU reports; windows are [start, end)."""
from datetime import datetime, time, timedelta
import re


def read_log(path):
    with open(path, errors="replace") as fh:
        for line in fh:
            fields = line.split(None, 1)
            if not fields or "T" not in fields[0]:
                continue
            try:
                stamp = datetime.fromisoformat(fields[0].replace("Z", "+00:00"))
            except ValueError:
                continue
            yield stamp, line


def window(path, since=None, until=None):
    first = last = None
    offsets = set()
    for stamp, _ in read_log(path):
        offsets.add(stamp.utcoffset())
        try:
            first = stamp if first is None else min(first, stamp)
            last = stamp if last is None else max(last, stamp)
        except TypeError:
            raise ValueError("mixed timezone-aware and local log timestamps") from None
    if first is None:
        raise ValueError("no data: no valid dated log timestamps")

    if since is None and until is None:
        start, end = first, last
    elif since is None or until is None:
        raise ValueError("supply both start and end timestamps")
    elif re.fullmatch(r"\d\d:\d\d:\d\d(?:\.\d+)?", since) and re.fullmatch(
        r"\d\d:\d\d:\d\d(?:\.\d+)?", until
    ):
        if len(offsets) != 1:
            raise ValueError("ambiguous local times: use full ISO timestamps with offsets")
        t0, t1 = time.fromisoformat(since), time.fromisoformat(until)
        if t0 == t1:
            raise ValueError("start and end must differ")
        overnight = t1 < t0
        day = first.date() - timedelta(days=overnight)
        candidates = []
        while day <= last.date():
            start = datetime.combine(day, t0, first.tzinfo)
            end = datetime.combine(day + timedelta(days=overnight), t1, first.tzinfo)
            if start < last and end > first:
                candidates.append((start, end))
            day += timedelta(days=1)
        if len(candidates) != 1:
            raise ValueError("ambiguous or absent clock-time window: use full ISO timestamps")
        start, end = candidates[0]
    else:
        try:
            start = datetime.fromisoformat(since.replace("Z", "+00:00"))
            end = datetime.fromisoformat(until.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("use HH:MM:SS or full ISO timestamps for both bounds") from None

    try:
        if end <= start:
            raise ValueError("end must be later than start")
        if start < first or end > last:
            raise ValueError(
                "insufficient evidence: log timestamps do not cover the full requested "
                f"window (available {first.isoformat()} .. {last.isoformat()})"
            )
    except TypeError:
        raise ValueError("window and log timestamps must use the same timezone style") from None
    return start, end
