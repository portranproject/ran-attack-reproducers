#!/usr/bin/env python3
"""Capture an immutable, run-scoped byte slice from one append-only DU log."""

import hashlib
import json
import os
from pathlib import Path
import re
import stat as stat_module
import sys


CHUNK = 1024 * 1024


def fail(message):
    raise ValueError(message)


def hash_prefix(handle, length):
    handle.seek(0)
    digest = hashlib.sha256()
    remaining = length
    while remaining:
        chunk = handle.read(min(CHUNK, remaining))
        if not chunk:
            fail("source became shorter while hashing its prefix")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def write_json_new(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def start(source_path, state_path):
    with Path(source_path).open("rb") as source:
        stat = os.fstat(source.fileno())
        if not stat_module.S_ISREG(stat.st_mode):
            fail("source is not a regular file")
        discard_leading_partial = False
        if stat.st_size:
            source.seek(stat.st_size - 1)
            discard_leading_partial = source.read(1) != b"\n"
        prefix_sha256 = hash_prefix(source, stat.st_size)
    write_json_new(state_path, {
        "schema_version": "rss.du-log-start.v1",
        "device": stat.st_dev,
        "inode": stat.st_ino,
        "start_offset": stat.st_size,
        "prefix_sha256": prefix_sha256,
        "discard_leading_partial": discard_leading_partial,
    })


def load_state(path):
    try:
        state = json.loads(Path(path).read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid start state: {exc}")
    if not isinstance(state, dict) or state.get("schema_version") != "rss.du-log-start.v1":
        fail("start state has the wrong schema")
    for key in ("device", "inode", "start_offset"):
        if type(state.get(key)) is not int or state[key] < 0:
            fail(f"start state has invalid {key}")
    if not isinstance(state.get("prefix_sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", state["prefix_sha256"]):
        fail("start state has invalid prefix_sha256")
    if type(state.get("discard_leading_partial", False)) is not bool:
        fail("start state has invalid discard_leading_partial")
    state["discard_leading_partial"] = state.get("discard_leading_partial", False)
    return state


def finish(source_path, state_path, slice_path, manifest_path):
    state = load_state(state_path)
    with Path(source_path).open("rb") as source:
        stat = os.fstat(source.fileno())
        if (stat.st_dev, stat.st_ino) != (state["device"], state["inode"]):
            fail("source rotated or was replaced")
        if stat.st_size < state["start_offset"]:
            fail("source was truncated")
        if hash_prefix(source, state["start_offset"]) != state["prefix_sha256"]:
            fail("source prefix changed after capture start")
        source.seek(state["start_offset"])
        expected = stat.st_size - state["start_offset"]
        raw = source.read(expected)
        if len(raw) != expected:
            fail("source changed while reading the run slice")
    discarded_leading = 0
    if state["discard_leading_partial"]:
        first_newline = raw.find(b"\n")
        if first_newline < 0:
            fail("run slice has no terminator for the pre-existing partial line")
        discarded_leading = first_newline + 1
    body = raw[discarded_leading:]
    last_newline = body.rfind(b"\n")
    if last_newline < 0:
        fail("run slice has no complete log line")
    complete = body[:last_newline + 1]
    with Path(slice_path).open("xb") as output:
        output.write(complete)
    digest = hashlib.sha256(complete).hexdigest()
    slice_start = state["start_offset"] + discarded_leading
    end_offset = slice_start + len(complete)
    write_json_new(manifest_path, {
        "schema_version": "rss.du-log-slice.v1",
        "device": state["device"],
        "inode": state["inode"],
        "capture_offset": state["start_offset"],
        "start_offset": slice_start,
        "end_offset": end_offset,
        "source_size_at_finish": stat.st_size,
        "discarded_leading_bytes": discarded_leading,
        "discarded_trailing_bytes": stat.st_size - end_offset,
        "sha256": digest,
    })


def main(argv):
    try:
        if len(argv) == 3 and argv[0] == "start":
            start(argv[1], argv[2])
        elif len(argv) == 5 and argv[0] == "finish":
            finish(argv[1], argv[2], argv[3], argv[4])
        else:
            print(
                "usage: capture_du_log.py start SOURCE STATE\n"
                "       capture_du_log.py finish SOURCE STATE SLICE MANIFEST",
                file=sys.stderr,
            )
            return 2
    except (OSError, ValueError) as exc:
        print(f"capture_du_log: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
