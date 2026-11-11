#!/usr/bin/env python3
"""분리된 탐지 입력과 oracle에서 단일 실행 판정을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SUBSTITUTED = "DOWNLINK_IMSI_EXTRACTOR event=identity_response_substituted"
CONTROL = "DOWNLINK_IMSI_EXTRACTOR event=authentication_response_submitted"
MESSAGES = {"RegistrationRequest", "IdentityRequest", "IdentityResponse", "AuthenticationRequest", "AuthenticationResponse"}


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 일반 파일이 아닙니다: {path.name}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return value


def load_observations(path: Path) -> list[dict]:
    text = regular(path).read_text(encoding="utf-8")
    if "suci-" in text.lower():
        raise ValueError("탐지 입력에 가입자 원문 또는 oracle 필드가 있습니다")
    rows = [json.loads(line) for line in text.splitlines() if line]
    if not rows:
        raise ValueError("관측 메시지가 비었습니다")
    required = {"schema", "order", "source", "direction", "message", "ran_ue_ngap_id", "amf_ue_ngap_id", "realtime_ns", "nas_security"}
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("관측 메시지 필드가 계약과 다릅니다")
        if row["schema"] != "downlink-imsi.observation.v1" or row["source"] != "ngap" or row["message"] not in MESSAGES:
            raise ValueError("관측 메시지 값이 잘못됐습니다")
        if row["direction"] not in {"uplink", "downlink"} or row["nas_security"] != "plain":
            raise ValueError("관측 방향 또는 NAS 보안 상태가 잘못됐습니다")
        if any(type(row[key]) is not int or row[key] < 0 for key in ("order", "ran_ue_ngap_id", "amf_ue_ngap_id", "realtime_ns")):
            raise ValueError("관측 순서·ID·시각이 잘못됐습니다")
    if [row["order"] for row in rows] != list(range(len(rows))) or any(a["realtime_ns"] > b["realtime_ns"] for a, b in zip(rows, rows[1:])):
        raise ValueError("관측 메시지가 시간순으로 정규화되지 않았습니다")
    if len({(row["ran_ue_ngap_id"], row["amf_ue_ngap_id"]) for row in rows}) != 1:
        raise ValueError("관측 메시지가 같은 UE context에 exact join되지 않았습니다")
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def verify(run_dir: Path) -> dict:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("실행 디렉터리가 없거나 심볼릭 링크입니다")
    run = load_object(run_dir / "run.json")
    process = load_object(run_dir / "process.json")
    service = load_object(run_dir / "service.json")
    oracle = load_object(run_dir / "oracle.json")
    observations = load_observations(run_dir / "observations.jsonl")
    ue_log = regular(run_dir / "ue.log").read_text(encoding="utf-8", errors="replace")
    pcap = regular(run_dir / "ngap.pcap")

    mode = run.get("mode")
    if run.get("schema") != "downlink-imsi.run.v1" or mode not in {"control", "emulation"}:
        raise ValueError("run 스키마 또는 mode가 잘못됐습니다")
    enabled = mode == "emulation"
    if run.get("identity_response_substitution_emulated") is not enabled or run.get("dl_overshadowing_observed") is not False:
        raise ValueError("원인·에뮬레이션 주장 경계가 잘못됐습니다")
    if process.get("schema") != "downlink-imsi.process.v1" or service.get("schema") != "downlink-imsi.service.v1" or oracle.get("schema") != "downlink-imsi.oracle.v1":
        raise ValueError("process/service/oracle 스키마가 잘못됐습니다")
    crash_free = process.get("crash_count") == 0 and process.get("forced_kill_count") == 0
    pcap_ok = pcap.stat().st_size > 24 and run.get("ngap_pcap_sha256") == sha256(pcap)

    names = [row["message"] for row in observations]
    counts = {name: names.count(name) for name in MESSAGES}
    try:
        registration_at = names.index("RegistrationRequest")
        authentication_at = names.index("AuthenticationRequest")
    except ValueError:
        registration_at = authentication_at = -1
    identity_at = names.index("IdentityResponse") if "IdentityResponse" in names else -1
    auth_response_at = names.index("AuthenticationResponse") if "AuthenticationResponse" in names else -1
    base_sequence = registration_at >= 0 and authentication_at > registration_at
    identity_request_absent = counts["IdentityRequest"] == 0
    substituted = ue_log.count(SUBSTITUTED)
    control_markers = ue_log.count(CONTROL)

    scheme = oracle.get("protection_scheme")
    if type(scheme) is not int or scheme not in {0, 1, 2}:
        raise ValueError("SUCI protection scheme이 잘못됐습니다")
    expected = oracle.get("expected_subscriber_fingerprint")
    observed = oracle.get("observed_subscriber_fingerprint")
    fingerprints_match = isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None and observed == expected
    null_exposure = enabled and scheme == 0 and fingerprints_match
    service_values = [service.get(key) for key in ("registration_ok", "pdu_session_ok", "ping_ok")]
    if any(type(value) is not bool for value in service_values):
        raise ValueError("서비스 판정은 boolean이어야 합니다")

    if mode == "control":
        control_healthy = base_sequence and auth_response_at > authentication_at and counts["AuthenticationResponse"] == 1 and counts["IdentityResponse"] == 0 and substituted == 0 and control_markers >= 1 and all(service_values)
        mechanism = unexpected = False
        passed = control_healthy and identity_request_absent and pcap_ok and crash_free
    else:
        control_healthy = False
        unexpected = base_sequence and identity_at > authentication_at and counts["IdentityResponse"] == 1 and identity_request_absent
        mechanism = unexpected and substituted == 1 and counts["AuthenticationResponse"] == 0
        passed = mechanism and pcap_ok and crash_free and (scheme != 0 or fingerprints_match)

    return {
        "schema": "downlink-imsi.verdict.v1",
        "run_id": run.get("run_id"),
        "mode": mode,
        "passed": passed,
        "control_healthy": control_healthy,
        "protocol_impact_reproduced": enabled and mechanism,
        "unexpected_identity_response_observed": enabled and unexpected,
        "suci_observed": enabled and counts["IdentityResponse"] == 1,
        "null_scheme_identity_exposure_observed": null_exposure,
        "service_effect_observed": enabled and not all(service_values),
        "dl_overshadowing_observed": False,
        "identity_response_substitution_emulated": enabled,
        "checks": {
            "authentication_request_count": counts["AuthenticationRequest"],
            "authentication_response_count": counts["AuthenticationResponse"],
            "identity_request_count": counts["IdentityRequest"],
            "identity_response_count": counts["IdentityResponse"],
            "substitution_marker_count": substituted,
            "control_marker_count": control_markers,
            "suci_protection_scheme": scheme,
            "subscriber_fingerprint_match": fingerprints_match,
            "ngap_pcap_nonempty_and_matched": pcap_ok,
            "crash_free": crash_free,
            "registration_ok": service_values[0],
            "pdu_session_ok": service_values[1],
            "ping_ok": service_values[2],
        },
    }


def write_manifest(run_dir: Path) -> None:
    output = run_dir / "evidence_manifest.json"
    if output.exists() or output.is_symlink():
        raise ValueError("기존 evidence manifest는 덮어쓰지 않습니다")
    names = ("run.json", "ue.log", "cu.log", "amf.log", "ngap.pcap", "observations.jsonl", "oracle.json", "service.json", "process.json", "verdict.json")
    files = {name: {"size": regular(run_dir / name).stat().st_size, "sha256": sha256(run_dir / name)} for name in names}
    output.write_text(json.dumps({"schema": "downlink-imsi.evidence.v1", "files": files}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


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
        write_manifest(root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"downlink-imsi 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
