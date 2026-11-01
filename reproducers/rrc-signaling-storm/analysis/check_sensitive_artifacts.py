#!/usr/bin/env python3
"""Fail closed on subscriber/auth values in files and common archives."""

import gzip
import json
import mmap
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import zipfile


MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_EXPANDED_BYTES = 2 * 1024 * 1024 * 1024
STREAM_CHUNK_BYTES = 1024 * 1024
STREAM_OVERLAP_BYTES = 1024
FIELD = re.compile(
    rb"(?i)\b(?P<field>imsi|supi|imeisv|ki|key|opc|sqn|amf)\s*[:=]\s*['\"]?"
    rb"(?P<value>[0-9a-f]+)"
)
DUMP = re.compile(
    rb"(?im)(?<![a-z0-9_])"
    rb"(?P<field>milenage output (?:ik|ck|res|autn)|opc|key|sqn|amf|rand)"
    rb"\s*:\s*(?P<value>(?:[0-9a-f]{2}[ \t]+)+)"
    rb"(?:\x1b\[[0-9;]*m)?[ \t]*\r?$"
)
DUMP_BYTES = {
    "opc": {16}, "key": {16}, "sqn": {6}, "amf": {2}, "rand": {16},
    "ik": {16}, "ck": {16}, "res": {8}, "autn": {8, 16},
}


def secret_fields(data):
    found = set()
    for match in FIELD.finditer(data):
        field = match.group("field").decode("ascii").casefold()
        value = match.group("value")
        if field in {"imsi", "supi", "imeisv"}:
            if value.isdigit() and 14 <= len(value) <= 17:
                found.add(field)
        elif field in {"ki", "key", "opc"} and len(value) == 32:
            found.add(field)
        elif field == "sqn" and len(value) == 12:
            found.add(field)
        elif field == "amf" and len(value) == 4:
            found.add(field)
    for match in DUMP.finditer(data):
        field = match.group("field").decode("ascii").casefold().rsplit(" ", 1)[-1]
        if len(match.group("value").split()) in DUMP_BYTES[field]:
            found.add(field)
    return found


def scan_stream(handle, label, limit=MAX_EXPANDED_BYTES):
    """Scan large compressed content without trusting its compressed size."""
    found = set()
    tail = b""
    total = 0
    while True:
        chunk = handle.read(STREAM_CHUNK_BYTES)
        if not chunk:
            return found
        total += len(chunk)
        if total > limit:
            raise ValueError(f"expanded content exceeds scan limit: {label}")
        data = tail + chunk
        found.update(secret_fields(data))
        tail = data[-STREAM_OVERLAP_BYTES:]


def scan_path(path):
    if path.is_symlink():
        return []  # Git stores the link target string, not the target file contents.
    if not path.is_file():
        raise ValueError(f"not a regular file: {path}")
    size = path.stat().st_size

    results = []
    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as archive:
            expanded = 0
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                label = f"{path}::{member.name}"
                expanded += member.size
                if expanded > MAX_EXPANDED_BYTES:
                    raise ValueError(f"expanded archive exceeds scan limit: {path}")
                handle = archive.extractfile(member)
                if handle is None:
                    raise ValueError(f"cannot read archive member: {label}")
                fields = scan_stream(handle, label)
                if fields:
                    results.append((label, fields))
        return results

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            expanded = 0
            for member in archive.infolist():
                if member.is_dir():
                    continue
                label = f"{path}::{member.filename}"
                expanded += member.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    raise ValueError(f"expanded archive exceeds scan limit: {path}")
                with archive.open(member) as handle:
                    fields = scan_stream(handle, label)
                if fields:
                    results.append((label, fields))
        return results

    if path.suffix.casefold() == ".gz":
        with gzip.open(path, "rb") as handle:
            fields = scan_stream(handle, str(path))
    elif size > MAX_FILE_BYTES:
        with path.open("rb") as handle, mmap.mmap(
                handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
            fields = secret_fields(data)
    else:
        fields = secret_fields(path.read_bytes())
    return [(str(path), fields)] if fields else []


def repository_paths():
    root = Path(subprocess.check_output(
        ["git", "-C", str(Path(__file__).resolve().parent),
         "rev-parse", "--show-toplevel"],
        text=True,
    ).strip())
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
         "--exclude-standard"]
    )
    return [root / item for item in output.decode().split("\0") if item]


def requested_paths(arguments):
    if not arguments:
        return repository_paths()
    paths = []
    for argument in arguments:
        path = Path(argument)
        if path.is_dir():
            paths.extend(item for item in path.rglob("*") if ".git" not in item.parts)
        else:
            paths.append(path)
    return paths


def main(argv):
    findings = []
    errors = []
    try:
        paths = requested_paths(argv)
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        print(f"sensitive-artifact-check: cannot enumerate files: {exc}", file=sys.stderr)
        return 1

    for path in sorted(set(paths), key=lambda item: str(item)):
        try:
            findings.extend(scan_path(path))
        except (OSError, EOFError, tarfile.TarError, zipfile.BadZipFile, ValueError) as exc:
            errors.append(str(exc))

    for label, fields in findings:
        print(
            "sensitive artifact: " + json.dumps(label) +
            " fields=" + ",".join(sorted(fields)),
            file=sys.stderr,
        )
    for error in errors:
        print(f"sensitive-artifact-check: {error}", file=sys.stderr)
    if findings or errors:
        return 1
    print(f"sensitive-artifact-check: ok ({len(paths)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
