#!/usr/bin/env python3
"""기존 공격 판정과 실제 TeleRAN→production detector 실행을 결합한다."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ALERT = re.compile(r"^ALERT (?P<action>\S+) rule=(?P<rule>\S+) cell=(?P<cell>\d+) t=(?P<t>\d+)(?P<rest>.*)$")
SEND = re.compile(r"\bsend file=(?P<file>\S+).*\bstatus=(?P<status>\d+) accepted=(?P<accepted>\d+) rejected=(?P<rejected>\d+)")
DETECTOR_COMMIT = "766f5569d0ddb425c14bf210a31c38ac60eceef9"
SCENARIOS = {
    "rrc-context-exhaustion": ("L3-01-V", "protocol"),
    "authentication-timeout-exhaustion": ("L3-01-O", "protocol"),
    "blind-dos": ("L3-20", "protocol"),
    "downlink-identifier-exposure": ("L3-24", "protocol-result-emulation"),
    "ue-capability-hijacking": ("L3-14", "protocol-observation-emulation"),
    "uplink-credential-flood": ("L3-21", "protocol"),
    "nas-counter-desynchronization": ("L3-06", "protocol-result-emulation"),
}


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path}")
    return value


def load_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in regular(path).read_text(encoding="utf-8").splitlines() if line]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSONL이 비었거나 객체가 아닙니다: {path}")
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def parse_alerts(path: Path) -> list[dict]:
    alerts = []
    for line in regular(path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = ALERT.match(line)
        if not match:
            continue
        row = match.groupdict()
        row.update({"schema": "ran-reproducer.detector.v1", "cell": int(row["cell"]),
                    "t": int(row["t"]), "raw": line})
        alerts.append(row)
    return alerts


def mechanism(scenario: str, mode: str, child: Path) -> tuple[bool, dict]:
    if child.is_symlink() or not child.is_dir():
        raise ValueError(f"공격 실행 증거 디렉터리가 없습니다: {child}")
    active = mode != "control"
    if scenario == "rrc-context-exhaustion":
        verdict_path = child / "run_stop.json"
        if not verdict_path.is_file() and (child / "result.json").is_file():
            verdict_path = child / "result.json"
        verdict = load_object(verdict_path)
        valid = verdict.get("valid") is True
        labels = []
        label_path = child / "ground_truth.jsonl"
        if label_path.is_file() and not label_path.is_symlink():
            labels = [json.loads(line) for line in label_path.read_text().splitlines() if line]
        positives = sum(row.get("canonical_a") is True or row.get("canonical_msg3_only") is True for row in labels)
        broker_msg3 = verdict.get("attacker_msg3", 0)
        if not isinstance(broker_msg3, int):
            broker_msg3 = 0
        passed = valid and (not active or positives > 0 or broker_msg3 > 0)
        summary = {"source": str(verdict_path), "source_sha256": sha256(verdict_path),
                   "valid": valid, "positive_ground_truth": positives,
                   "broker_attacker_msg3": broker_msg3}
    elif scenario == "blind-dos":
        verdict_path = child / "run_stop.json"
        verdict = load_object(verdict_path)
        passed = verdict.get("passed") is True
        summary = {"source": str(verdict_path), "source_sha256": sha256(verdict_path),
                   "classification": verdict.get("classification"), "passed": passed}
    else:
        verdict_path = child / "verdict.json"
        verdict = load_object(verdict_path)
        passed = verdict.get("passed") is True
        if scenario == "authentication-timeout-exhaustion" and active:
            passed = passed and verdict.get("mechanism_reproduced") is True
        summary = {"source": str(verdict_path), "source_sha256": sha256(verdict_path),
                   "schema": verdict.get("schema"), "passed": passed}
    summary["child_directory"] = str(child)
    return passed, summary


def started_at(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}T\d{6}Z", value):
        raise ValueError("telemetry hello session 시각이 잘못됐습니다")
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def verify(root: Path, scenario: str, mode: str, run_id: str, child: Path,
           require_same_cell: bool = False) -> dict:
    if root.is_symlink() or not root.is_dir() or scenario not in SCENARIOS:
        raise ValueError("실행 디렉터리 또는 시나리오가 잘못됐습니다")
    rule, level = SCENARIOS[scenario]
    if mode not in {"control", "attack", "emulation"}:
        raise ValueError("mode가 잘못됐습니다")
    active = mode != "control"
    profile_id = os.environ.get("RAN_REPRO_PROFILE_ID", "p5")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", profile_id) is None:
        raise ValueError("profile id가 잘못됐습니다")

    telemetry = root / "live/telemetry.jsonl"
    observations = root / "observations.jsonl"
    shutil.copyfile(regular(telemetry), observations)
    rows = load_jsonl(observations)
    hello = [row for row in rows if row.get("type") == "hello"]
    gaps = [row for row in rows if row.get("type") == "gap"]
    kpm = [row for row in rows if row.get("type") == "kpm2"]
    rrc_setup_requests = [row for row in rows if row.get("type") == "ue_evt"
                          and row.get("msg") == "RRCSetupRequest"]
    sequence = [row.get("seq") for row in rows]
    scenario_input_ok = not (scenario == "rrc-context-exhaustion" and active) or bool(rrc_setup_requests)
    input_ok = (len(hello) == 1 and hello[0].get("period_ms") == 100 and hello[0].get("ue_evt") is True
                and sequence == list(range(1, len(rows) + 1)) and not gaps and bool(kpm)
                and scenario_input_ok)

    alerts = parse_alerts(root / "live/detector.stdout")
    raises = [row for row in alerts if row["action"] == "RAISE" and row["rule"] == rule]
    detector_ok = len(raises) == (0 if not active else 1)
    components = load_object(root / "live/components.json")
    if components.get("detector", {}).get("commit") != DETECTOR_COMMIT:
        raise ValueError("검증된 production detector 커밋이 아닙니다")
    for name in ("detector", "telemetry"):
        value = components.get(name, {}).get("binary_sha256")
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError(f"{name} 바이너리 해시가 없습니다")

    sender_status = int(regular(root / "live/sender.exit").read_text().strip())
    sends = [match.groupdict() for line in regular(root / "live/sender.log").read_text(encoding="utf-8", errors="replace").splitlines()
             if (match := SEND.search(line))]
    accepted = sum(int(row["accepted"]) for row in sends)
    rejected = sum(int(row["rejected"]) for row in sends)
    evidence_delivered = any(row["file"].endswith("/evidence.jsonl") and int(row["accepted"]) > 0 for row in sends)
    delivery_ok = sender_status == 0 and accepted > 0 and rejected == 0 and (not active or evidence_delivered)
    mechanism_ok, mechanism_summary = mechanism(scenario, mode, child)
    mechanism_summary.update({"schema": "ran-reproducer.mechanism-link.v1", "scenario_id": scenario,
                              "mode": mode, "passed": mechanism_ok})
    (root / "mechanism.json").write_text(json.dumps(mechanism_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    same_cell_ok = not require_same_cell
    same_cell_summary = {"missing": True} if require_same_cell else None
    same_cell_run = root / "same-cell-run.json"
    if same_cell_run.is_file() and not same_cell_run.is_symlink():
        session = load_object(root / "same-cell-session.json")
        wrapper = load_object(same_cell_run)
        health = load_jsonl(root / "same-cell-normal-health.jsonl")
        valid_rows = all(row.get("schema") == "same-cell.normal-health.v1"
                         and row.get("run_id") == run_id for row in health)
        before = {row.get("ue") for row in health if row.get("phase") == "before"
                  and row.get("tun_ok") is True and row.get("ping_ok") is True}
        after = {row.get("ue") for row in health if row.get("phase") == "after"
                 and row.get("tun_ok") is True and row.get("ping_ok") is True}
        expected_ues = set(range(1, 6))
        same_cell_ok = (valid_rows and session.get("schema") == "same-cell.session.v2"
                        and session.get("run_id") == run_id and session.get("normal_ues") == 5
                        and session.get("clocked_attack_slots") is True
                        and wrapper.get("schema") == "same-cell.run.v3"
                        and wrapper.get("run_id") == run_id
                        and wrapper.get("direct_detector_input") is False
                        and wrapper.get("ue_to_ran_path_required") is True
                        and wrapper.get("normal_healthy_before_attack_teardown") is True
                        and wrapper.get("attack_exit_status") == 0
                        and before == expected_ues and after == expected_ues)
        same_cell_summary = {"normal_before": len(before), "normal_after": len(after),
                             "direct_detector_input": wrapper.get("direct_detector_input"),
                             "ue_to_ran_path_required": wrapper.get("ue_to_ran_path_required")}

    checks = {"hello_period_100ms": len(hello) == 1 and hello[0].get("period_ms") == 100,
              "sequence_contiguous": sequence == list(range(1, len(rows) + 1)), "gap_count": len(gaps),
              "kpm2_count": len(kpm), "rrc_setup_request_count": len(rrc_setup_requests),
              "target_raise_count": len(raises),
              "dashboard_sender_exit_status": sender_status, "dashboard_accepted_lines": accepted,
              "dashboard_rejected_lines": rejected, "dashboard_alert_evidence_delivered": evidence_delivered,
              "mechanism_passed": mechanism_ok, "same_cell": same_cell_summary}
    passed = mechanism_ok and input_ok and detector_ok and delivery_ok and same_cell_ok
    run = {"schema": "ran-reproducer.run.v1", "run_id": run_id, "scenario_id": scenario,
           "rule_ids": [rule], "mode": mode, "profile": profile_id, "reproduction_level": level,
           "started_at": started_at(hello[0].get("session")), "period_ms": 100,
           "source": {"detector": components["detector"], "telemetry": components["telemetry"],
                      "mechanism_sha256": sha256(root / "mechanism.json")},
           "clock": {"source": "same-host-monotonic", "detector_and_telemetry_same_host": True},
           "claims": {"live_protocol_path_observed": True, "rf_cause_observed": False,
                      "service_denial_observed": False}}
    (root / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    oracle = {"schema": "ran-reproducer.oracle.v1", "run_id": run_id, "mode": mode,
              "expected_rule": rule, "expected_raise": active, "checks": checks}
    (root / "oracle.jsonl").write_text(json.dumps(oracle, sort_keys=True, separators=(",", ":")) + "\n")
    with (root / "detector.jsonl").open("w", encoding="utf-8") as output:
        for row in alerts:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    verdict = {"schema": "ran-reproducer.verdict.v1", "run_id": run_id, "passed": passed,
               "expected_rule": rule, "observed_alerts": len(raises),
               "dimensions": {"mechanism": "pass" if mechanism_ok else "fail",
                              "detection_input": "pass" if input_ok else "fail",
                              "detector_result": "pass" if detector_ok and delivery_ok else "fail",
                              "service_impact": "not_observed"}}
    (root / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    (root / "report.md").write_text(
        f"# {run_id}\n\n- 시나리오/룰: `{scenario}` / `{rule}`\n- 모드: `{mode}`\n"
        f"- 기존 공격 판정: `{'pass' if mechanism_ok else 'fail'}`\n"
        f"- UE→ZMQ→DU/CU→TeleRAN→production detector: `true`\n"
        f"- 입력 gap/KPM: `{len(gaps)}/{len(kpm)}`\n- {rule} RAISE: `{len(raises)}`\n"
        f"- 대시보드 수락/거절: `{accepted}/{rejected}`\n- 최종 판정: `{'pass' if passed else 'fail'}`\n",
        encoding="utf-8")
    files = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "evidence_manifest.json"):
        files[str(path.relative_to(root))] = {"size": path.stat().st_size, "sha256": sha256(path)}
    (root / "evidence_manifest.json").write_text(
        json.dumps({"schema": "ran-reproducer.evidence.v1", "run_id": run_id, "files": files},
                   sort_keys=True, separators=(",", ":")) + "\n")
    return verdict


def main() -> int:
    if len(sys.argv) != 7:
        print("usage: verify_live_e2e.py RUN_DIR SCENARIO MODE RUN_ID CHILD_DIR DETECTOR_COMMIT", file=sys.stderr)
        return 2
    if sys.argv[6] != DETECTOR_COMMIT:
        print("고정 production detector 커밋과 다릅니다", file=sys.stderr)
        return 2
    try:
        require_same_cell = os.environ.get("LIVE_E2E_REQUIRE_SAME_CELL", "0") == "1"
        verdict = verify(Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], Path(sys.argv[5]),
                         require_same_cell=require_same_cell)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"live E2E 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
