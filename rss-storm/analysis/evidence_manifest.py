#!/usr/bin/env python3
"""Seal and verify one rss-run directory without reading secret config files."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


SCHEMA = "rss.evidence-manifest.v1"
MANIFEST = "evidence_manifest.json"
ARTIFACTS = (
    "attempts.jsonl",
    "du_log_capture.err",
    "du_log_slice.json",
    "du_log_start.json",
    "gnb_boot.txt",
    "gnb_ready.txt",
    "gnb_stop.txt",
    "ground_truth.jsonl",
    "odu.log",
    "run.json",
    "run_stop.json",
    "sensitive_artifact_check.err",
    "sensitive_artifact_check.txt",
    "ue.log",
    "ue_redaction.err",
    "ue_redaction.json",
)
REQUIRED = {
    "run.json", "run_stop.json", "ground_truth.jsonl", "ue.log",
    "ue_redaction.json", "sensitive_artifact_check.txt",
}
SHA256 = re.compile(r"[0-9a-f]{64}")


def fail(message):
    raise ValueError(message)


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path, label):
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def regular_file(path, label):
    if path.is_symlink() or not path.is_file():
        fail(f"{label} is not a regular file")


def atomic_create(path, value):
    if path.exists() or path.is_symlink():
        fail(f"{path.name} already exists")
    with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp = Path(handle.name)
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temp, path)
    except FileExistsError:
        fail(f"{path.name} already exists")
    finally:
        temp.unlink(missing_ok=True)


def enforce_current_sensitive_policy(run_dir):
    scanner = Path(__file__).with_name("check_sensitive_artifacts.py")
    regular_file(scanner, "current sensitive artifact scanner")
    result = subprocess.run(
        [sys.executable, str(scanner), str(run_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        fail(f"current sensitive artifact scan failed (exit {result.returncode})")


def seal(run_dir):
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        fail("run directory is not a real directory")
    run = load_object(run_dir / "run.json", "run.json")
    stopped = load_object(run_dir / "run_stop.json", "run_stop.json")
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id or stopped.get("run_id") != run_id:
        fail("run.json and run_stop.json run_id do not match")

    files = []
    for name in ARTIFACTS:
        path = run_dir / name
        if not path.exists() and not path.is_symlink():
            continue
        regular_file(path, name)
        files.append({
            "path": name,
            "size": path.stat().st_size,
            "sha256": hash_file(path),
        })
    missing = REQUIRED - {item["path"] for item in files}
    if missing:
        fail("missing required artifacts: " + ", ".join(sorted(missing)))
    enforce_current_sensitive_policy(run_dir)
    atomic_create(run_dir / MANIFEST, {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": files,
    })
    return run_id, len(files)


def load_labels(path, run_id):
    rows = []
    seen = set()
    try:
        handle = path.open(errors="strict")
    except OSError as exc:
        fail(f"cannot read ground_truth.jsonl: {exc}")
    with handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(f"ground_truth.jsonl line {number} is malformed: {exc}")
            if not isinstance(row, dict) or row.get("run_id") != run_id:
                fail(f"ground_truth.jsonl line {number} has the wrong run_id")
            attempt_id = row.get("attempt_id")
            if not isinstance(attempt_id, str) or attempt_id in seen:
                fail(f"ground_truth.jsonl line {number} has a missing or duplicate attempt_id")
            seen.add(attempt_id)
            rows.append(row)
    return rows


def verify_software(run):
    software = run.get("software")
    if not isinstance(software, dict):
        fail("run.json has no software provenance")
    for key in (
        "ue_binary_sha256", "rss_patch_sha256", "runner_sha256",
        "label_exporter_sha256", "du_capture_sha256", "log_redactor_sha256",
        "artifact_scanner_sha256",
    ):
        if not isinstance(software.get(key), str) or not SHA256.fullmatch(software[key]):
            fail(f"run.json has invalid software.{key}")
    commit = software.get("ue_commit")
    if commit != "unknown" and (
            not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit)):
        fail("run.json has invalid software.ue_commit")
    return software


def verify_label_replay(run_dir, software, expected_digest):
    exporter = Path(__file__).with_name("export_labels.py")
    regular_file(exporter, "current label exporter")
    if hash_file(exporter) != software["label_exporter_sha256"]:
        fail("current label exporter does not match run.json provenance")
    with tempfile.NamedTemporaryFile() as replay:
        result = subprocess.run(
            [sys.executable, str(exporter), str(run_dir / "run.json"),
             str(run_dir / "attempts.jsonl"), str(run_dir / "odu.log")],
            stdout=replay, stderr=subprocess.PIPE, check=False,
        )
        replay.flush()
        if result.returncode != 0:
            fail(f"matched label replay failed (exit {result.returncode})")
        if hash_file(Path(replay.name)) != expected_digest:
            fail("ground_truth.jsonl does not match replayed raw evidence")


def verify(run_dir, require_matched=False):
    run_dir = Path(run_dir)
    manifest = load_object(run_dir / MANIFEST, MANIFEST)
    if manifest.get("schema_version") != SCHEMA:
        fail("evidence manifest has the wrong schema")
    run_id = manifest.get("run_id")
    entries = manifest.get("files")
    if not isinstance(run_id, str) or not run_id or not isinstance(entries, list):
        fail("evidence manifest has invalid metadata")

    recorded = {}
    for item in entries:
        if not isinstance(item, dict):
            fail("evidence manifest file entry is not an object")
        name, size, digest = item.get("path"), item.get("size"), item.get("sha256")
        if name not in ARTIFACTS or name in recorded:
            fail("evidence manifest has an unknown or duplicate path")
        if type(size) is not int or size < 0 or not isinstance(digest, str) \
                or not SHA256.fullmatch(digest):
            fail(f"evidence manifest has invalid metadata for {name}")
        path = run_dir / name
        regular_file(path, name)
        if path.stat().st_size != size or hash_file(path) != digest:
            fail(f"artifact hash or size mismatch: {name}")
        recorded[name] = digest
    missing = REQUIRED - set(recorded)
    if missing:
        fail("evidence manifest omits required artifacts: " + ", ".join(sorted(missing)))
    for name in ARTIFACTS:
        path = run_dir / name
        if (path.exists() or path.is_symlink()) and name not in recorded:
            fail(f"evidence manifest omits existing artifact: {name}")
    enforce_current_sensitive_policy(run_dir)

    run = load_object(run_dir / "run.json", "run.json")
    stopped = load_object(run_dir / "run_stop.json", "run_stop.json")
    if run.get("run_id") != run_id or stopped.get("run_id") != run_id:
        fail("cross-file run_id mismatch")
    software = verify_software(run)
    redaction = load_object(run_dir / "ue_redaction.json", "ue_redaction.json")
    if redaction.get("schema_version") != "rss.ue-log-redaction.v1" \
            or redaction.get("run_id") != run_id:
        fail("UE log redaction report has inconsistent metadata")
    if redaction.get("status") not in {
            "clean", "redacted", "truncated_oversized", "truncated_residual"}:
        fail("UE log redaction report has an unknown status")
    if type(redaction.get("redacted_lines")) is not int \
            or redaction["redacted_lines"] < 0:
        fail("UE log redaction report has an invalid line count")
    if redaction.get("output_sha256") != recorded["ue.log"]:
        fail("UE log redaction hash does not match the sealed log")
    if stopped.get("valid") is True and redaction.get("status") != "clean":
        fail("valid run required UE log redaction")
    try:
        scan_result = (run_dir / "sensitive_artifact_check.txt").read_text()
    except (OSError, UnicodeError) as exc:
        fail(f"cannot read sensitive artifact check result: {exc}")
    if stopped.get("sensitive_artifact_scan") != "ok" \
            or not scan_result.startswith("sensitive-artifact-check: ok ("):
        fail("run lacks a successful pre-seal sensitive artifact scan")
    rows = load_labels(run_dir / "ground_truth.jsonl", run_id)
    positives = [row for row in rows if row.get("canonical_a") is True]
    join = stopped.get("du_ack_join")

    if join in {"matched", "no_match"}:
        if not {"odu.log", "du_log_slice.json"} <= set(recorded):
            fail("successful DU slice status lacks sealed DU artifacts")
        slice_info = load_object(run_dir / "du_log_slice.json", "du_log_slice.json")
        digest = recorded["odu.log"]
        if slice_info.get("sha256") != digest or stopped.get("du_log_sha256") != digest:
            fail("DU slice SHA-256 does not match manifest and run_stop")
    if join == "matched":
        if "attempts.jsonl" not in recorded:
            fail("matched status lacks sealed attempts.jsonl")
        if stopped.get("valid") is not True or stopped.get("label_export") != "ok" or not positives:
            fail("matched status lacks a valid exported RRCSetupComplete-omission label")
        orchestration = run.get("orchestration")
        sector = orchestration.get("du_sector_id") if isinstance(orchestration, dict) else None
        if type(sector) is not int:
            fail("matched status lacks du_sector_id")
        for row in positives:
            evidence = row.get("du_ack_evidence")
            if not isinstance(evidence, dict) or evidence.get("log_sha256") != recorded["odu.log"] \
                    or evidence.get("sector_id") != sector:
                fail("RRCSetupComplete-omission label has inconsistent DU evidence")
        verify_label_replay(run_dir, software, recorded["ground_truth.jsonl"])
    elif positives:
        fail("RRCSetupComplete-omission labels exist without du_ack_join=matched")
    if require_matched and join != "matched":
        fail(f"DU ACK join is {join!r}, not matched")
    return run_id, len(recorded), len(positives)


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "seal":
            run_id, count = seal(argv[1])
            print(f"evidence-manifest: sealed run_id={run_id} files={count}")
        elif len(argv) in (2, 3) and argv[0] == "verify" \
                and (len(argv) == 2 or argv[2] == "--require-matched"):
            run_id, count, positives = verify(argv[1], len(argv) == 3)
            print(
                f"evidence-manifest: verified run_id={run_id} "
                f"files={count} canonical_a={positives}"
            )
        else:
            print(
                "usage: evidence_manifest.py seal RUN_DIR\n"
                "       evidence_manifest.py verify RUN_DIR [--require-matched]",
                file=sys.stderr,
            )
            return 2
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"evidence-manifest: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
