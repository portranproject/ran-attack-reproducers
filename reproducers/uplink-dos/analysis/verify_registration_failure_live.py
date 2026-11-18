#!/usr/bin/env python3
"""실제 UE→ZMQ→DU/CU→계측→탐지 실행을 판정하고 봉인한다."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


SEQUENCE = ("RRCSetupRequest", "RRCSetup", "RRCSetupComplete", "RegistrationRequest", "RegistrationReject")
ALERT = re.compile(r"^ALERT (?P<action>\S+) rule=(?P<rule>\S+) cell=(?P<cell>\d+) t=(?P<t>\d+)(?P<rest>.*)$")
SEND = re.compile(r"\bsend file=(?P<file>\S+).*\bstatus=(?P<status>\d+) accepted=(?P<accepted>\d+) rejected=(?P<rejected>\d+)")
DETECTOR_COMMIT = "766f5569d0ddb425c14bf210a31c38ac60eceef9"


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path}")
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in regular(path).read_text(encoding="utf-8").splitlines() if line]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSONL이 비었거나 객체가 아닙니다: {path}")
    return rows


def join_rotated_jsonl(path: Path, output: Path) -> list[dict]:
    rotated = sorted(item for item in path.parent.glob(path.name + ".*")
                     if re.fullmatch(r"\d{8}-\d{6}", item.name.removeprefix(path.name + ".")))
    inputs = [regular(item) for item in rotated] + [regular(path)]
    output.write_text("".join(item.read_text(encoding="utf-8") for item in inputs), encoding="utf-8")
    return jsonl(output)


def parse_alerts(path: Path) -> list[dict]:
    alerts = []
    for line in regular(path).read_text(encoding="utf-8", errors="replace").splitlines():
        match = ALERT.match(line)
        if not match:
            continue
        row = match.groupdict()
        row.update({"schema": "ran-reproducer.detector.v1", "cell": int(row["cell"]), "t": int(row["t"]), "raw": line})
        alerts.append(row)
    return alerts


def failed_contexts(events: list[dict]) -> list[list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in events:
        groups[(row.get("cell_id"), row.get("du_ue_id"), row.get("crnti"))].append(row)
    return [rows for rows in groups.values() if any(row.get("msg") == "RegistrationReject" for row in rows)]


def session_started_at(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{8}T\d{6}Z", value):
        raise ValueError("telemetry hello session 시각이 잘못됐습니다")
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def verify(root: Path, mode: str, run_id: str, binary: Path, ue_config: Path, uecap: Path, flood_patch: Path) -> dict:
    if root.is_symlink() or not root.is_dir() or mode not in {"control", "attack"}:
        raise ValueError("실행 디렉터리 또는 mode가 잘못됐습니다")
    detector_config = json.loads(regular(root / "live/detector.config.json").read_text(encoding="utf-8"))
    l3_21 = detector_config.get("rules", {}).get("L3-21", {})
    threshold = max(l3_21.get("n_fail", 0), math.ceil(l3_21.get("n_fail_frac", 0) * l3_21.get("max_conn", 0)))
    if threshold != 10 or l3_21.get("fail_accept_wait_ms") != 3000:
        raise ValueError("L3-21 production 기준은 n_fail_th=10, fail_accept_wait_ms=3000이어야 합니다")
    plan = json.loads(regular(root / "ue-plan.json").read_text(encoding="utf-8"))
    ue_count = plan.get("ue_count")
    target_per_ue = plan.get("target_per_ue")
    expected = plan.get("expected_rejects")
    if ue_count != 1 or target_per_ue != (1 if mode == "control" else threshold):
        raise ValueError("UE 실행 계획이 mode 또는 L3-21 기준과 맞지 않습니다")
    if expected != ue_count * target_per_ue or mode == "attack" and expected != threshold:
        raise ValueError("UE 실행 계획의 목표 거절 수가 잘못됐습니다")
    observations = root / "observations.jsonl"
    rows = join_rotated_jsonl(root / "live/detector-input.jsonl", observations)
    telemetry = root / "live/telemetry.jsonl"
    if sha256(observations) != sha256(telemetry):
        raise ValueError("계측 원문과 탐지 엔진 입력 기록이 다릅니다")
    profile_id = os.environ.get("RAN_REPRO_PROFILE_ID", "p5")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", profile_id) is None:
        raise ValueError("profile id가 잘못됐습니다")
    hello = [row for row in rows if row.get("type") == "hello"]
    seq = [row.get("seq") for row in rows]
    gaps = [row for row in rows if row.get("type") == "gap"]
    kpm = [row for row in rows if row.get("type") == "kpm2"]
    events = [row for row in rows if row.get("type") == "ue_evt"]
    groups = failed_contexts(events)
    attack_events = [row for group in groups for row in group]
    requests = [row for row in attack_events if row.get("msg") == "RegistrationRequest"]
    rejects = [row for row in attack_events if row.get("msg") == "RegistrationReject"]
    accepts = [row for row in attack_events if row.get("msg") == "RegistrationAccept"]
    complete = 0
    for group in groups:
        names = [row.get("msg") for row in group]
        positions = [names.index(name) if name in names else -1 for name in SEQUENCE]
        complete += positions == sorted(positions) and all(position >= 0 for position in positions)
    span_ms = rejects[-1]["t_ms"] - rejects[0]["t_ms"] if rejects else None
    alerts = parse_alerts(root / "live/detector.stdout")
    raises = [row for row in alerts if row["action"] == "RAISE" and row["rule"] == "L3-21"]
    branch1 = [row for row in raises if " branch=1 " in f" {row['raw']} "
               and f" n_fail_th={threshold} " in f" {row['raw']} "]
    ue_log = regular(root / "ue.log").read_text(encoding="utf-8", errors="replace")
    markers = ue_log.count("UPLINK_DOS_DETECTION event=registration_failure")
    ue_rejects = ue_log.count("Received Registration Reject cause")
    crashes = len(re.findall(r"Segmentation fault|Assertion|Caught signal|core dumped", ue_log))
    status = int(regular(root / "ue.exit").read_text().strip())
    components = json.loads(regular(root / "live/components.json").read_text(encoding="utf-8"))
    sender_status = int(regular(root / "live/sender.exit").read_text().strip())
    sends = [match.groupdict() for line in regular(root / "live/sender.log").read_text(encoding="utf-8", errors="replace").splitlines()
             if (match := SEND.search(line))]
    dashboard_accepted = sum(int(row["accepted"]) for row in sends)
    dashboard_rejected = sum(int(row["rejected"]) for row in sends)
    evidence_delivered = any(row["file"].endswith("/evidence.jsonl") and int(row["accepted"]) > 0 for row in sends)
    checks = {
        "hello_period_100ms": len(hello) == 1 and hello[0].get("period_ms") == 100 and hello[0].get("ue_evt") is True,
        "sequence_contiguous": seq == list(range(1, len(rows) + 1)),
        "gap_count": len(gaps),
        "kpm2_count": len(kpm),
        "complete_f1_n2_contexts": complete,
        "registration_request_count": len(requests),
        "registration_reject_count": len(rejects),
        "registration_accept_count": len(accepts),
        "reject_span_ms": span_ms,
        "ue_failure_marker_count": markers,
        "ue_reject_count": ue_rejects,
        "ue_exit_status": status,
        "crash_count": crashes,
        "l3_21_raise_count": len(raises),
        "l3_21_branch1_raise_count": len(branch1),
        "dashboard_sender_exit_status": sender_status,
        "dashboard_accepted_lines": dashboard_accepted,
        "dashboard_rejected_lines": dashboard_rejected,
        "dashboard_alert_evidence_delivered": evidence_delivered,
    }
    passed = (
        checks["hello_period_100ms"] and checks["sequence_contiguous"] and not gaps and kpm
        and complete == expected and len(requests) == expected and len(rejects) == expected and not accepts
        and span_ms is not None and span_ms < 10_000 and markers == expected
        and ue_rejects == expected and status == 0 and crashes == 0
        and len(raises) == (0 if mode == "control" else 1)
        and len(branch1) == (0 if mode == "control" else 1)
        and sender_status == 0 and dashboard_accepted > 0 and dashboard_rejected == 0
        and (mode == "control" or evidence_delivered)
    )
    for name, values in (("detector", components.get("detector")), ("telemetry", components.get("telemetry"))):
        if not isinstance(values, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(values.get("binary_sha256", ""))):
            raise ValueError(f"{name} 구성요소 해시가 없습니다")
    if not re.fullmatch(r"[0-9a-f]{64}", str(components.get("dashboard", {}).get("sender_sha256", ""))):
        raise ValueError("dashboard sender 해시가 없습니다")
    if components["detector"].get("commit") != DETECTOR_COMMIT:
        raise ValueError("검증된 production detector 커밋이 아닙니다")

    run = {
        "schema": "ran-reproducer.run.v1", "run_id": run_id, "scenario_id": "uplink-credential-flood",
        "rule_ids": ["L3-21"], "mode": mode, "profile": profile_id, "reproduction_level": "protocol",
        "started_at": session_started_at(hello[0].get("session")), "period_ms": 100,
        "source": {
            "ue_binary_sha256": sha256(binary), "ue_config_sha256": sha256(ue_config),
            "ue_runtime_config_sha256": sha256(root / "ue-runtime.conf") if (root / "ue-runtime.conf").is_file() else sha256(ue_config),
            "uecap_sha256": sha256(uecap), "flood_patch_sha256": sha256(flood_patch),
            "detector": components["detector"], "telemetry": components["telemetry"],
        },
        "logical_ues": ue_count,
        "clock": {"source": "realtime", "detector_and_telemetry_same_host": True},
        "claims": {"live_protocol_path_observed": True, "rf_cause_observed": False, "service_denial_observed": False},
    }
    (root / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    oracle = {"schema": "ran-reproducer.oracle.v1", "run_id": run_id, "mode": mode,
              "ue_failure_marker_count": markers, "ue_reject_count": ue_rejects, "crash_count": crashes,
              "checks": checks}
    (root / "oracle.jsonl").write_text(json.dumps(oracle, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    with (root / "detector.jsonl").open("w", encoding="utf-8") as output:
        for row in alerts:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    verdict = {
        "schema": "ran-reproducer.verdict.v1", "run_id": run_id, "passed": bool(passed), "expected_rule": "L3-21",
        "observed_alerts": len(raises), "dimensions": {"mechanism": "pass" if passed else "fail",
        "detection_input": "pass" if checks["hello_period_100ms"] and checks["sequence_contiguous"] and not gaps else "fail",
        "detector_result": "pass" if len(raises) == (0 if mode == "control" else 1) else "fail",
        "service_impact": "not_observed"},
    }
    (root / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "report.md").write_text(
        f"# {run_id}\n\n- 모드: `{mode}`\n- 실제 UE→ZMQ→DU/CU→계측→탐지: `true`\n"
        f"- 논리 UE 수: `{ue_count}`\n"
        f"- RegistrationRequest/Reject: `{len(requests)}/{len(rejects)}`\n- Reject span: `{span_ms} ms`\n"
        f"- L3-21 기준/RAISE: `{threshold}/{len(raises)}`\n- 대시보드 수락/거절: `{dashboard_accepted}/{dashboard_rejected}`\n"
        f"- 판정: `{'pass' if passed else 'fail'}`\n"
        "- RF 송신 우위와 서비스 거부는 주장하지 않음\n", encoding="utf-8")
    files = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "evidence_manifest.json"):
        relative = str(path.relative_to(root))
        files[relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
    manifest = {"schema": "ran-reproducer.evidence.v1", "run_id": run_id, "files": files}
    (root / "evidence_manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return verdict


def main() -> int:
    if len(sys.argv) != 8:
        print("usage: verify_registration_failure_live.py RUN_DIR MODE RUN_ID OAI_BIN UE_CFG UECAP FLOOD_PATCH", file=sys.stderr)
        return 2
    try:
        verdict = verify(Path(sys.argv[1]), sys.argv[2], sys.argv[3], *(Path(value) for value in sys.argv[4:]))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"live 자격증명 실패 플러드 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
