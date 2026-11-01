#!/usr/bin/env python3
"""Remove subscriber/auth values from one UE log before evidence sealing."""

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from check_sensitive_artifacts import MAX_FILE_BYTES, secret_fields


MARKER = b"[REDACTED subscriber/auth material]"
SCHEMA = "rss.ue-log-redaction.v1"


def fail(message):
    raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_replace(path, data, mode):
    with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        os.fchmod(handle.fileno(), mode)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_report(path, value):
    if path.exists() or path.is_symlink():
        fail("redaction report already exists")
    with path.open("x") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def line_ending(line):
    if line.endswith(b"\r\n"):
        return b"\r\n"
    if line.endswith(b"\n"):
        return b"\n"
    if line.endswith(b"\r"):
        return b"\r"
    return b""


def sanitize(log_path, report_path, run_id):
    log_path = Path(log_path)
    report_path = Path(report_path)
    if log_path.is_symlink() or not log_path.is_file():
        fail("UE log is not a regular file")
    metadata = log_path.stat()
    mode = stat.S_IMODE(metadata.st_mode)
    if metadata.st_size > MAX_FILE_BYTES:
        output = b"[REDACTED oversized UE log; run invalid]\n"
        atomic_replace(log_path, output, mode)
        status = "truncated_oversized"
        redacted_lines = 0
    else:
        data = log_path.read_bytes()
        lines = []
        redacted_lines = 0
        for line in data.splitlines(keepends=True):
            if secret_fields(line):
                lines.append(MARKER + line_ending(line))
                redacted_lines += 1
            else:
                lines.append(line)
        output = b"".join(lines)
        if secret_fields(output):
            output = b"[REDACTED UE log with residual sensitive material; run invalid]\n"
            status = "truncated_residual"
        elif redacted_lines:
            status = "redacted"
        else:
            status = "clean"
        if output != data:
            atomic_replace(log_path, output, mode)

    write_report(report_path, {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "status": status,
        "redacted_lines": redacted_lines,
        "input_size": metadata.st_size,
        "output_size": len(output),
        "output_sha256": digest(output),
    })
    print(f"ue-log-redaction: status={status} redacted_lines={redacted_lines}")
    return status == "clean"


def main(argv):
    if len(argv) != 3:
        print("usage: sanitize_ue_log.py UE_LOG REPORT_JSON RUN_ID", file=sys.stderr)
        return 2
    try:
        clean = sanitize(*argv)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ue-log-redaction: {exc}", file=sys.stderr)
        return 1
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
