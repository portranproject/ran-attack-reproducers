#!/usr/bin/env python3
"""위조 자격증명 실패 플러드 탐지 입력 에뮬레이션을 판정·봉인한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


SEQUENCE = ("RRCSetupRequest", "RRCSetup", "RRCSetupComplete", "RegistrationRequest", "RegistrationReject")


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path.name}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def load_observations(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in regular(path).read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError("관측 입력이 비었습니다")
    for order, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("schema") != "uplink-dos.registration-failure-observation.v1" or row.get("order") != order:
            raise ValueError("관측 스키마·순서가 잘못됐습니다")
        if row.get("source") not in {"detector-input-emulation", "f1ap"}:
            raise ValueError("관측 출처가 잘못됐습니다")
    return rows


def verify(run_dir: Path) -> dict:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("실행 디렉터리가 없거나 심볼릭 링크입니다")
    run = load_object(run_dir / "run.json")
    detection = load_object(run_dir / "l3-21-verdict.json")
    rows = load_observations(run_dir / "observations.jsonl")
    replay = regular(run_dir / "detector-input.jsonl")
    mode = run.get("mode")
    enabled = mode == "emulation"
    if run.get("schema") != "uplink-dos.registration-failure-emulation.v1" or mode not in {"control", "emulation"}:
        raise ValueError("run 스키마 또는 mode가 잘못됐습니다")
    limits = {"registration_failure_flood_emulated": enabled, "rf_overshadowing_observed": False, "live_protocol_path_observed": False}
    if any(run.get(key) is not value for key, value in limits.items()):
        raise ValueError("에뮬레이션 주장 경계가 잘못됐습니다")
    if run.get("detector_input_sha256") != sha256(replay):
        raise ValueError("탐지 입력 해시가 다릅니다")

    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("gnb_du_ue_f1ap_id"), row.get("crnti"))].append(row)
    complete = 0
    for group in groups.values():
        names = [row.get("message") for row in group]
        positions = [names.index(name) if name in names else -1 for name in SEQUENCE]
        complete += all(position >= 0 for position in positions) and positions == sorted(positions)
    requests = sum(row.get("message") == "RegistrationRequest" for row in rows)
    rejects = [row for row in rows if row.get("message") == "RegistrationReject"]
    accepts = sum(row.get("message") == "RegistrationAccept" for row in rows)
    expected = 5 if enabled else 1
    span_ms = (rejects[-1]["realtime_ns"] - rejects[0]["realtime_ns"]) // 1_000_000 if rejects else None
    signal_ok = complete == expected and requests == expected and len(rejects) == expected and accepts == 0 and span_ms is not None and span_ms < 10000
    hashes = (detection.get("detector_sha256"), detection.get("detector_config_sha256"))
    detection_ok = (detection.get("schema") == "uplink-dos.l3-21-verdict.v1" and detection.get("mode") == mode
                    and detection.get("passed") is True and all(isinstance(value, str) and len(value) == 64 for value in hashes))
    passed = signal_ok and detection_ok
    return {
        "schema": "uplink-dos.registration-failure-verdict.v1", "run_id": run.get("run_id"), "mode": mode,
        "passed": passed, "l3_21_signal_emulated": enabled and signal_ok, "detector_alert_verified": detection_ok,
        "detector_sha256": hashes[0], "detector_config_sha256": hashes[1],
        "rf_overshadowing_observed": False, "live_protocol_path_observed": False,
        "checks": {"complete_contexts": complete, "registration_request_count": requests,
                   "registration_reject_count": len(rejects), "registration_accept_count": accepts,
                   "reject_span_ms": span_ms, "l3_21_raise_count": detection.get("l3_21_raise_count"),
                   "l3_21_branch1_raise_count": detection.get("l3_21_branch1_raise_count")},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        root = args.run_dir.resolve()
        verdict = verify(root)
        output = root / "verdict.json"
        if output.exists() or output.is_symlink():
            raise ValueError("기존 verdict는 덮어쓰지 않습니다")
        output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        names = ("run.json", "observations.jsonl", "detector-input.jsonl", "l3-21-verdict.json", "verdict.json")
        files = {name: {"size": regular(root / name).stat().st_size, "sha256": sha256(root / name)} for name in names}
        manifest = root / "evidence_manifest.json"
        if manifest.exists() or manifest.is_symlink():
            raise ValueError("기존 evidence manifest는 덮어쓰지 않습니다")
        manifest.write_text(json.dumps({"schema": "uplink-dos.registration-failure-evidence.v1", "files": files}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"위조 자격증명 실패 플러드 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
