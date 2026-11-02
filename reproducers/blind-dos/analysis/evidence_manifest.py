#!/usr/bin/env python3
"""Immutably seal and verify one Blind DoS run directory."""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import stat
import sys

from export_labels import atomic_create, load_object, validate_final, validate_run


SCHEMA = "blind.evidence-manifest.v1"
MANIFEST = "evidence_manifest.json"
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED = {
    "run.json", "run_stop.json", "attacker_events.jsonl", "victim_service.jsonl",
    "target_snapshot_before.json", "target_snapshot_after.json", "amf.log", "cu.log",
    "du.log", "ngap.pcap", "f1ap.pcap", "ground_truth.jsonl",
}
MINIMUM = {"run.json", "run_stop.json"}


def fail(message):
    raise ValueError(message)


def hash_file(path):
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        fail(f"{path.name} is not a regular file")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat(follow_symlinks=False)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != \
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        fail(f"{path.name} changed while it was being hashed")
    return after.st_size, digest.hexdigest()


def inventory(run_dir, required):
    files = []
    for path in sorted(run_dir.iterdir(), key=lambda item: item.name):
        if path.name == MANIFEST:
            continue
        if path.is_symlink():
            fail(f"run directory contains a symlink: {path.name}")
        if not path.is_file():
            fail(f"run directory contains a non-file entry: {path.name}")
        size, digest = hash_file(path)
        files.append({"path": path.name, "size": size, "sha256": digest})
    present = {item["path"] for item in files}
    missing = required - present
    if missing:
        fail("missing required artifacts: " + ", ".join(sorted(missing)))
    return files


def seal(run_dir):
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        fail("run directory is not a real directory")
    manifest_path = run_dir / MANIFEST
    if manifest_path.exists() or manifest_path.is_symlink():
        fail(f"{MANIFEST} already exists")
    stopped = load_object(run_dir / "run_stop.json", "run_stop.json")
    classification = stopped.get("classification")
    if classification == "infrastructure-invalid":
        _, run_id, mode, _ = validate_run(run_dir / "run.json")
        if stopped.get("schema_version") != "blind.run-stop.v1" \
                or stopped.get("run_id") != run_id or stopped.get("mode") != mode:
            fail("run_stop.json does not match run.json")
        required = MINIMUM
    else:
        run_id, classification, _ = validate_final(run_dir)
        required = REQUIRED
    files = inventory(run_dir, required)
    atomic_create(manifest_path, {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "classification": classification,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": files,
    })
    return run_id, len(files)


def verify(run_dir):
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        fail("run directory is not a real directory")
    manifest = load_object(run_dir / MANIFEST, MANIFEST)
    if manifest.get("schema_version") != SCHEMA:
        fail("evidence manifest has the wrong schema")
    run_id = manifest.get("run_id")
    classification = manifest.get("classification")
    entries = manifest.get("files")
    if not isinstance(run_id, str) or not run_id or classification not in {
            "passed", "valid-failure", "infrastructure-invalid"} \
            or not isinstance(entries, list):
        fail("evidence manifest has invalid metadata")

    recorded = {}
    for item in entries:
        if not isinstance(item, dict):
            fail("evidence manifest file entry is not an object")
        name, size, digest = item.get("path"), item.get("size"), item.get("sha256")
        if not isinstance(name, str) or not name or Path(name).name != name \
                or name == MANIFEST or name in recorded:
            fail("evidence manifest has an unsafe or duplicate path")
        if type(size) is not int or size < 0 or not isinstance(digest, str) \
                or not SHA256.fullmatch(digest):
            fail(f"evidence manifest has invalid metadata for {name}")
        path = run_dir / name
        if path.is_symlink() or not path.is_file():
            fail(f"sealed artifact is missing or not a regular file: {name}")
        actual_size, actual_digest = hash_file(path)
        if actual_size != size or actual_digest != digest:
            fail(f"artifact hash or size mismatch: {name}")
        recorded[name] = digest
    required = MINIMUM if classification == "infrastructure-invalid" else REQUIRED
    missing = required - set(recorded)
    if missing:
        fail("evidence manifest omits required artifacts: " + ", ".join(sorted(missing)))

    current = {path.name for path in run_dir.iterdir() if path.name != MANIFEST}
    if current != set(recorded):
        added = current - set(recorded)
        removed = set(recorded) - current
        detail = []
        if added:
            detail.append("unsealed=" + ",".join(sorted(added)))
        if removed:
            detail.append("missing=" + ",".join(sorted(removed)))
        fail("run directory contents changed after seal: " + " ".join(detail))

    if classification == "infrastructure-invalid":
        _, final_run_id, mode, _ = validate_run(run_dir / "run.json")
        stopped = load_object(run_dir / "run_stop.json", "run_stop.json")
        if stopped.get("schema_version") != "blind.run-stop.v1" \
                or stopped.get("run_id") != final_run_id \
                or stopped.get("mode") != mode \
                or stopped.get("classification") != classification:
            fail("manifest metadata does not match run metadata")
    else:
        final_run_id, final_classification, _ = validate_final(run_dir)
        if final_run_id != run_id or final_classification != classification:
            fail("manifest metadata does not match run metadata")
    return run_id, len(recorded)


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "seal":
            run_id, count = seal(argv[1])
            print(f"blind-evidence: sealed run_id={run_id} files={count}")
        elif len(argv) == 2 and argv[0] == "verify":
            run_id, count = verify(argv[1])
            print(f"blind-evidence: verified run_id={run_id} files={count}")
        else:
            print(
                "usage: evidence_manifest.py seal RUN_DIR\n"
                "       evidence_manifest.py verify RUN_DIR",
                file=sys.stderr,
            )
            return 2
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"blind-evidence: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
