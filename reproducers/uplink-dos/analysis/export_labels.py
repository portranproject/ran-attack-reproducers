#!/usr/bin/env python3
"""봉인된 원문에서 uplink DoS 프로토콜 영향 재현 판정을 만든다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MARKER = "UPLINK_DOS_EMULATION event=service_request_mac_corrupted"
CORE_REQUEST_TOKENS = ("Service request", "Service Request", "SERVICEREQUEST")
CORE_MAC_FAILURE = "NAS MAC verification failed"
UE_SERVICE_REJECT = "Received NAS Service Reject message"


def fail(message: str) -> None:
    raise ValueError(message)


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        fail(f"필수 원문이 없거나 일반 파일이 아닙니다: {path.name}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"JSON 객체가 아닙니다: {path.name}")
    return value


def load_rows(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(regular(path).read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            fail(f"service.jsonl {number}행이 잘못됐습니다: {error}")
        if not isinstance(row, dict):
            fail(f"service.jsonl {number}행이 객체가 아닙니다")
        rows.append(row)
    return rows


def consecutive_failures(rows: list[dict]) -> int:
    best = current = 0
    for row in rows:
        current = current + 1 if row["ping_ok"] is False else 0
        best = max(best, current)
    return best


def consecutive_successes(rows: list[dict]) -> int:
    best = current = 0
    for row in rows:
        current = current + 1 if row["ping_ok"] is True else 0
        best = max(best, current)
    return best


def verify(run_dir: Path) -> dict:
    if run_dir.is_symlink() or not run_dir.is_dir():
        fail("실행 디렉터리가 없거나 심볼릭 링크입니다")
    run = load_object(run_dir / "run.json")
    process = load_object(run_dir / "process.json")
    rows = load_rows(run_dir / "service.jsonl")
    ue_log = regular(run_dir / "ue.log").read_text(encoding="utf-8", errors="replace")
    cu_log = regular(run_dir / "cu.log").read_text(encoding="utf-8", errors="replace")
    amf_log = regular(run_dir / "amf.log").read_text(encoding="utf-8", errors="replace")

    if run.get("schema") != "uplink-dos.run.v1":
        fail("run.json 스키마가 다릅니다")
    mode = run.get("mode")
    enabled = run.get("emulation_enabled")
    if mode not in {"control", "emulation"} or enabled is not (mode == "emulation"):
        fail("mode와 emulation_enabled가 일치하지 않습니다")
    if process.get("schema") != "uplink-dos.process.v1":
        fail("process.json 스키마가 다릅니다")
    if process.get("victim_pid") != run.get("victim_pid"):
        fail("피해 UE PID가 실행 메타데이터와 다릅니다")

    phases = {name: [row for row in rows if row.get("phase") == name] for name in ("baseline", "impact", "recovery")}
    for name, phase_rows in phases.items():
        if len(phase_rows) < 5:
            fail(f"{name} 단계 ping 표본이 5개 미만입니다")
        for row in phase_rows:
            if row.get("schema") != "uplink-dos.service.v1" or type(row.get("ping_ok")) is not bool:
                fail(f"{name} 단계 서비스 행이 잘못됐습니다")
            if row.get("victim_pid") != run.get("victim_pid"):
                fail("동일 피해 UE 프로세스 조건을 만족하지 않습니다")

    marker_count = ue_log.count(MARKER)
    baseline_ok = all(row["ping_ok"] for row in phases["baseline"])
    recovery_streak = consecutive_successes(phases["recovery"])
    recovery_ok = recovery_streak >= 5
    crash_free = process.get("crash_count") == 0 and process.get("forced_kill_count") == 0
    initial_ue_messages = sum(
        "Tx PDU" in line and "InitialUEMessage" in line for line in cu_log.splitlines()
    )
    gnb_path = initial_ue_messages >= 2
    core_request = any(token in amf_log for token in CORE_REQUEST_TOKENS)
    core_effect = CORE_MAC_FAILURE in amf_log
    service_reject = UE_SERVICE_REJECT in ue_log
    network_path = gnb_path and core_request and core_effect and service_reject
    loss_streak = consecutive_failures(phases["impact"])
    impact_successes = sum(row["ping_ok"] for row in phases["impact"])

    if mode == "control":
        impact_ok = impact_successes >= len(phases["impact"]) - 2 and loss_streak <= 2
        passed = baseline_ok and marker_count == 0 and impact_ok and recovery_ok and crash_free
    else:
        impact_ok = loss_streak >= 5
        passed = baseline_ok and marker_count == 1 and network_path and impact_ok and recovery_ok and crash_free

    return {
        "schema": "uplink-dos.verdict.v1",
        "run_id": run.get("run_id"),
        "mode": mode,
        "passed": passed,
        "protocol_impact_reproduced": mode == "emulation" and marker_count == 1,
        "network_effect_observed": mode == "emulation" and network_path,
        "victim_service_loss_observed": mode == "emulation" and impact_ok,
        "same_victim_recovered": recovery_ok,
        "rf_overshadowing_observed": False,
        "checks": {
            "baseline_healthy": baseline_ok,
            "service_request_substitution_count": marker_count,
            "gnb_path_observed": gnb_path,
            "gnb_initial_ue_message_count": initial_ue_messages,
            "core_request_observed": core_request,
            "core_effect_observed": core_effect,
            "ue_service_reject_observed": service_reject,
            "max_consecutive_ping_failures": loss_streak,
            "impact_ping_successes": impact_successes,
            "max_consecutive_recovery_successes": recovery_streak,
            "crash_free": crash_free,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        verdict = verify(args.run_dir.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"uplink-dos 판정 실패: {error}", file=sys.stderr)
        return 2
    output = args.run_dir / "verdict.json"
    output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
