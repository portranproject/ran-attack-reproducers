#!/usr/bin/env python3
"""Exact 48-bit 5G-S-TMSI encoding used by the Blind DoS UE patch."""

import json
import re
import sys


FULL_BITS = 48
PART1_BITS = 39
PART2_BITS = 9
FULL_MAX = (1 << FULL_BITS) - 1
PART1_MAX = (1 << PART1_BITS) - 1
PART2_MAX = (1 << PART2_BITS) - 1
_CANONICAL = re.compile(r"0x[0-9a-fA-F]{12}")


def _integer(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{label} must be an integer in 0..{maximum}")
    return value


def parse_5g_s_tmsi(value):
    """Return an exact 48-bit value from an integer or 0x + 12 hex digits."""
    if type(value) is int:
        return _integer(value, "5G-S-TMSI", FULL_MAX)
    if not isinstance(value, str) or not _CANONICAL.fullmatch(value):
        raise ValueError("5G-S-TMSI must be exactly 0x followed by 12 hex digits")
    return int(value[2:], 16)


def format_5g_s_tmsi(value):
    return f"0x{parse_5g_s_tmsi(value):012x}"


def split_5g_s_tmsi(value):
    """Return (ng-5G-S-TMSI-Part1, Part2) as low 39 and high 9 bits."""
    full = parse_5g_s_tmsi(value)
    return full & PART1_MAX, (full >> PART1_BITS) & PART2_MAX


def join_5g_s_tmsi(part1, part2):
    """Reconstruct the 48-bit value without truncating either component."""
    part1 = _integer(part1, "Part1", PART1_MAX)
    part2 = _integer(part2, "Part2", PART2_MAX)
    return (part2 << PART1_BITS) | part1


# Names used in the implementation plan and in small external verification hooks.
canonical_hex = format_5g_s_tmsi
build_5g_s_tmsi = join_5g_s_tmsi


def _parse_component(value, label):
    try:
        return int(value, 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "split":
            full = parse_5g_s_tmsi(argv[1])
            part1, part2 = split_5g_s_tmsi(full)
        elif len(argv) == 3 and argv[0] == "join":
            part1 = _parse_component(argv[1], "Part1")
            part2 = _parse_component(argv[2], "Part2")
            full = join_5g_s_tmsi(part1, part2)
        else:
            print(
                "usage: identity.py split 0x0123456789ab\n"
                "       identity.py join PART1 PART2",
                file=sys.stderr,
            )
            return 2
        print(json.dumps({
            "schema_version": "blind.identity.v1",
            "target_5g_s_tmsi": format_5g_s_tmsi(full),
            "part1": part1,
            "part2": part2,
        }, sort_keys=True, separators=(",", ":")))
    except ValueError as exc:
        print(f"identity: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
