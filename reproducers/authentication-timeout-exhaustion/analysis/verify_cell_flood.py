#!/usr/bin/env python3
"""한 셀 인증 무응답 플러드의 UE oracle을 판정한다."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


MARKERS = {
    "control": "AUTH_TIMEOUT_EXHAUSTION event=authentication_response_submitted",
    "attack": "AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld",
}


def load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path}")
    return value


def verify(root: Path, mode: str, run_id: str, expected: int) -> dict:
    if root.is_symlink() or not root.is_dir() or mode not in MARKERS or expected < 1:
        raise ValueError("실행 디렉터리·mode·UE 수가 잘못됐습니다")
    run = load(root / "run.json")
    process = load(root / "process.json")
    if run.get("schema") != "auth-timeout.cell-flood-run.v1" or run.get("run_id") != run_id or run.get("mode") != mode:
        raise ValueError("run 계약이 다릅니다")
    process_count = run.get("process_count")
    ues_per_process = run.get("ues_per_process")
    logs = sorted(root.glob("ue-*.log"))
    if (not isinstance(process_count, int) or not isinstance(ues_per_process, int)
            or process_count * ues_per_process != expected or len(logs) != process_count
            or any(path.is_symlink() or not path.is_file() for path in logs)):
        raise ValueError("UE 로그 수가 실행 계획과 다릅니다")
    marker_counts = []
    for path in logs:
        text = path.read_text(errors="replace")
        marker_counts.append(len(set(re.findall(re.escape(MARKERS[mode]) + r" ue=(\d+)", text))))
    crashes = sum(len(re.findall(r"Segmentation fault|Assertion.*failed|Backtrace|core dumped", path.read_text(errors="replace"))) for path in logs)
    clean = (process.get("schema") == "auth-timeout.cell-flood-process.v1"
             and process.get("early_exit_count") == 0 and process.get("forced_kill_count") == 0
             and process.get("recovery_signal_count", 0) == 0 and crashes == 0)
    mechanism = marker_counts == [ues_per_process] * process_count
    passed = clean and mechanism
    return {"schema": "auth-timeout.cell-flood-verdict.v1", "run_id": run_id, "mode": mode,
            "passed": passed, "mechanism_reproduced": mode == "attack" and mechanism,
            "resource_accumulation_observed": False,
            "checks": {"planned_ue_count": expected, "marker_count": sum(marker_counts),
                       "one_marker_per_ue": mechanism,
                       "early_exit_count": process.get("early_exit_count"),
                       "forced_kill_count": process.get("forced_kill_count"),
                       "recovery_signal_count": process.get("recovery_signal_count", 0), "crash_count": crashes}}


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: verify_cell_flood.py RUN_DIR control|attack RUN_ID EXPECTED_UE", file=sys.stderr)
        return 2
    try:
        verdict = verify(Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]))
        output = Path(sys.argv[1]) / "verdict.json"
        if output.exists() or output.is_symlink():
            raise ValueError("기존 verdict는 덮어쓰지 않습니다")
        output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"한 셀 인증 고갈 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
