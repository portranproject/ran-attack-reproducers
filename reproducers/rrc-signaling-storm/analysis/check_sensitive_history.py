#!/usr/bin/env python3
"""Fail closed on subscriber/auth values reachable from any local Git ref."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from check_sensitive_artifacts import MAX_FILE_BYTES, scan_path


OBJECT_ID = re.compile(rb"[0-9a-f]{40,64}")


def reachable_objects(root):
    output = subprocess.check_output(
        ["git", "-C", str(root), "rev-list", "-z", "--objects", "--all"]
    )
    objects = {}
    current = None
    for record in output.split(b"\0"):
        if not record:
            continue
        if OBJECT_ID.fullmatch(record):
            current = record.decode("ascii")
            objects.setdefault(current, set())
        elif record.startswith(b"path=") and current is not None:
            objects[current].add(record[5:].decode("utf-8", errors="surrogateescape"))
        else:
            raise ValueError("cannot parse git rev-list --objects output")
    return objects


def object_metadata(root, object_ids):
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch-check="
         "%(objectname) %(objecttype) %(objectsize)"],
        input="".join(f"{oid}\n" for oid in object_ids),
        text=True, capture_output=True, check=True,
    )
    metadata = {}
    for line in result.stdout.splitlines():
        oid, object_type, size = line.split()
        metadata[oid] = (object_type, int(size))
    if set(metadata) != set(object_ids):
        raise ValueError("git cat-file did not describe every reachable object")
    return metadata


def scan_blob(root, oid, paths):
    suffix = ".gz" if any(path.casefold().endswith(".gz") for path in paths) else ""
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", oid],
            stdout=handle, stderr=subprocess.PIPE, check=True,
        )
        handle.flush()
        temporary = str(Path(handle.name))
        results = []
        for label, fields in scan_path(Path(handle.name)):
            member = label[len(temporary):] if label.startswith(temporary) else ""
            for path in sorted(paths) or ["<unpathed>"]:
                results.append((f"git:{oid}:{path}{member}", fields))
        return results


def scan_repository(root):
    objects = reachable_objects(root)
    metadata = object_metadata(root, objects)
    findings = []
    errors = []
    blobs = 0
    for oid in sorted(objects):
        object_type, size = metadata[oid]
        if object_type != "blob":
            continue
        blobs += 1
        if size > MAX_FILE_BYTES:
            errors.append(f"unscanned oversized Git blob: {oid} ({size} bytes)")
            continue
        try:
            findings.extend(scan_blob(root, oid, objects[oid]))
        except (OSError, EOFError, subprocess.SubprocessError, tarfile.TarError,
                zipfile.BadZipFile, ValueError) as exc:
            errors.append(f"cannot scan Git blob {oid}: {exc}")
    return blobs, findings, errors


def main(argv):
    if len(argv) > 1:
        print("usage: check_sensitive_history.py [REPOSITORY]", file=sys.stderr)
        return 2
    root = Path(argv[0]) if argv else Path(subprocess.check_output(
        ["git", "-C", str(Path(__file__).resolve().parent),
         "rev-parse", "--show-toplevel"],
        text=True,
    ).strip())
    try:
        subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True,
        )
        blobs, findings, errors = scan_repository(root)
    except (OSError, UnicodeError, subprocess.SubprocessError, ValueError) as exc:
        print(f"sensitive-history-check: cannot scan repository: {exc}", file=sys.stderr)
        return 1

    for label, fields in findings:
        print(
            "sensitive Git blob: " + json.dumps(label) +
            " fields=" + ",".join(sorted(fields)),
            file=sys.stderr,
        )
    for error in errors:
        print(f"sensitive-history-check: {error}", file=sys.stderr)
    if findings or errors:
        print(
            f"sensitive-history-check: scanned {blobs} reachable blobs; "
            f"findings={len(findings)} errors={len(errors)}",
            file=sys.stderr,
        )
        return 1
    print(f"sensitive-history-check: ok ({blobs} reachable blobs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
