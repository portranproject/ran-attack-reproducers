#!/usr/bin/env python3
"""정규화된 원문에서 인증 미응답 컨텍스트 고갈 판정을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

INPUTS = (
    "run.json", "profiles.manifest.json", "phase_inputs.json", "attacker_map.json", "attacker_truth.jsonl", "contexts.jsonl",
    "service.jsonl", "process.json", "ue.log", "cu.log", "amf.log",
)


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"필수 원문이 없거나 일반 파일이 아닙니다: {path.name}")
    return path


def load_object(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path.name}")
    return value


def load_rows(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(regular(path).read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} {number}행이 객체가 아닙니다")
        rows.append(value)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with regular(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def active_peak(contexts: list[dict]) -> int:
    points = []
    for row in contexts:
        created, released = row.get("created_realtime_ns"), row.get("released_realtime_ns")
        if type(created) is not int or type(released) is not int or created >= released:
            raise ValueError("컨텍스트 생성·해제 시각이 잘못됐습니다")
        points.extend(((created, 1), (released, -1)))
    current = peak = 0
    for _, delta in sorted(points, key=lambda point: (point[0], point[1])):
        current += delta
        peak = max(peak, current)
    return peak


def active_at(contexts: list[dict], timestamp: int) -> int:
    return sum(row["created_realtime_ns"] <= timestamp < row["released_realtime_ns"] for row in contexts)


def service_ok(row: dict) -> bool:
    return all(row.get(key) is True for key in ("registration_ok", "pdu_session_ok", "ping_ok"))


def service_failed(row: dict) -> bool:
    return row.get("registration_ok") is False and row.get("pdu_session_ok") is False and row.get("ping_ok") is False


def verify(run_dir: Path) -> dict:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("실행 디렉터리가 없거나 심볼릭 링크입니다")
    run = load_object(run_dir / "run.json")
    profiles = load_object(run_dir / "profiles.manifest.json")
    phase_inputs = load_object(run_dir / "phase_inputs.json")
    attacker_map = load_object(run_dir / "attacker_map.json")
    process = load_object(run_dir / "process.json")
    truth = load_rows(run_dir / "attacker_truth.jsonl")
    contexts = load_rows(run_dir / "contexts.jsonl")
    service = load_rows(run_dir / "service.jsonl")
    for name in ("ue.log", "cu.log", "amf.log"):
        regular(run_dir / name)

    if run.get("schema") != "auth-timeout.run.v1" or profiles.get("schema") != "auth-timeout.profiles.v1":
        raise ValueError("run 또는 profile manifest 스키마가 다릅니다")
    if phase_inputs.get("schema") != "auth-timeout.phase-inputs.v1" or not isinstance(phase_inputs.get("files"), dict):
        raise ValueError("phase input 스키마가 다릅니다")
    phase_file_keys = set(phase_inputs["files"])
    required_phase_files = {"uecap", "ue_endpoints", "p5_hook", "service_probe"}
    if phase_file_keys != required_phase_files or any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None for value in phase_inputs["files"].values()
    ):
        raise ValueError("phase input 해시가 잘못됐습니다")
    if run.get("profile_manifest_sha256") != sha256(run_dir / "profiles.manifest.json"):
        raise ValueError("run에 고정한 profile manifest 해시가 다릅니다")
    for key in ("gnb_config_sha256", "core_config_sha256", "phase_driver_sha256", "ue_patch_sha256", "ru_sharing_patch_sha256", "ue_binary_sha256", "zmq_library_sha256", "runtime_config_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", str(run.get(key))) is None:
            raise ValueError(f"실행 provenance 해시가 잘못됐습니다: {key}")
    if type(run.get("start_interval_ms")) is not int or run["start_interval_ms"] <= 0:
        raise ValueError("공격자 시작 간격이 잘못됐습니다")
    mode = run.get("mode")
    enabled = run.get("withholding_enabled")
    if mode not in {"control", "attack"} or enabled is not (mode == "attack"):
        raise ValueError("mode와 withholding_enabled가 일치하지 않습니다")
    attacker_profiles = [row for row in profiles.get("profiles", []) if row.get("role") == "attacker"]
    witness_profiles = [row for row in profiles.get("profiles", []) if row.get("role") == "witness"]
    expected = {row.get("subscriber_fingerprint") for row in attacker_profiles}
    mapped = attacker_map.get("attackers") if attacker_map.get("schema") == "auth-timeout.attacker-map.v1" else None
    if not isinstance(mapped, list) or len(mapped) != len(attacker_profiles):
        raise ValueError("attacker log mapping이 없거나 공격자 수와 다릅니다")
    if {row.get("subscriber_fingerprint") for row in mapped} != expected:
        raise ValueError("attacker log mapping이 profile manifest와 다릅니다")
    for row in mapped:
        if re.fullmatch(r"[0-9a-f]{64}", str(row.get("log_sha256"))) is None or Path(str(row.get("log_file"))).name != row.get("log_file"):
            raise ValueError("attacker log mapping의 파일명 또는 해시가 잘못됐습니다")
        if sha256(run_dir / row["log_file"]) != row["log_sha256"]:
            raise ValueError(f"attacker UE 로그 해시가 mapping과 다릅니다: {row['log_file']}")
    if len(witness_profiles) != 1 or None in expected or len(expected) != profiles.get("attacker_count"):
        raise ValueError("profile manifest의 역할 또는 fingerprint가 잘못됐습니다")
    if run.get("attacker_count") != len(expected) or len(expected) < 2:
        raise ValueError("run의 공격자 수가 profile manifest와 다릅니다")
    witness = witness_profiles[0].get("subscriber_fingerprint")

    if {row.get("subscriber_fingerprint") for row in truth} != expected or len(truth) != len(expected):
        raise ValueError("공격자 정답이 profile manifest와 exact match되지 않습니다")
    if {row.get("subscriber_fingerprint") for row in contexts} != expected or len(contexts) < len(expected):
        raise ValueError("모든 공격 가입자의 망 컨텍스트가 필요합니다")
    for row in truth:
        if row.get("schema") != "auth-timeout.truth.v1":
            raise ValueError("공격자 정답 스키마가 다릅니다")
    for row in contexts:
        if row.get("schema") != "auth-timeout.context.v1":
            raise ValueError("망 컨텍스트 스키마가 다릅니다")
        if not all(row.get(key) is True for key in ("rrc_setup_complete", "initial_ue_message", "authentication_request")):
            raise ValueError("RRC→NGAP 컨텍스트와 UE Authentication Request 처리 조인이 불완전합니다")
        if type(row.get("ran_ue_ngap_id")) is not int or type(row.get("amf_ue_ngap_id")) is not int:
            raise ValueError("NGAP ID 조인이 없습니다")
    if len({row["ran_ue_ngap_id"] for row in contexts}) != len(contexts) or len({row["amf_ue_ngap_id"] for row in contexts}) != len(contexts):
        raise ValueError("서로 다른 공격 연결이 같은 NGAP ID로 병합됐습니다")

    phases = {phase: sorted((row for row in service if row.get("phase") == phase), key=lambda row: row.get("attempt", 0)) for phase in ("baseline", "impact", "recovery")}
    if len(phases["baseline"]) < 1 or len(phases["impact"]) != 5 or len(phases["recovery"]) != 5:
        raise ValueError("witness 표본은 baseline 1회 이상, impact 5회, recovery 5회여야 합니다")
    for phase_rows in phases.values():
        for row in phase_rows:
            if row.get("schema") != "auth-timeout.service.v1" or row.get("witness_fingerprint") != witness:
                raise ValueError("witness 서비스 행이 profile manifest와 다릅니다")
            if type(row.get("realtime_ns")) is not int or type(row.get("elapsed_ms")) is not int:
                raise ValueError("witness 서비스 시각 또는 지연이 없습니다")
    limit = run.get("registration_limit_ms")
    if type(limit) is not int or limit < 10_000:
        raise ValueError("사전 고정 등록 제한시간이 잘못됐습니다")

    crash_free = process.get("schema") == "auth-timeout.process.v1" and process.get("crash_count") == 0 and process.get("forced_kill_count") == 0
    baseline_ok = all(service_ok(row) for row in phases["baseline"])
    recovery_ok = all(service_ok(row) and (mode == "control" or row["elapsed_ms"] <= limit) for row in phases["recovery"])
    peak = active_peak(contexts)
    withholding_count = sum(row.get("withheld_request_count", 0) for row in truth)
    context_counts = {
        fingerprint: sum(row.get("subscriber_fingerprint") == fingerprint for row in contexts)
        for fingerprint in expected
    }
    if mode == "control":
        protocol_ok = withholding_count == 0 and all(
            row.get("response_submitted") is True
            and row.get("submitted_response_count", 0) >= context_counts[row.get("subscriber_fingerprint")]
            for row in truth
        )
        impact_ok = all(service_ok(row) for row in phases["impact"])
        passed = protocol_ok and baseline_ok and impact_ok and recovery_ok and crash_free
        accumulation = False
    else:
        protocol_ok = all(
            row.get("withheld_request_count", 0) >= context_counts[row.get("subscriber_fingerprint")]
            and row.get("response_submitted") is False
            and row.get("submitted_response_count", 0) == 0
            for row in truth
        )
        accumulation = protocol_ok and peak >= len(expected)
        impact_ok = all(
            service_failed(row) and row["elapsed_ms"] >= limit
            and active_at(contexts, row["realtime_ns"]) >= len(expected)
            for row in phases["impact"]
        )
        passed = accumulation and baseline_ok and impact_ok and recovery_ok and crash_free

    return {
        "schema": "auth-timeout.verdict.v1",
        "run_id": run.get("run_id"),
        "mode": mode,
        "passed": passed,
        "mechanism_reproduced": mode == "attack" and protocol_ok,
        "resource_accumulation_observed": mode == "attack" and accumulation,
        "witness_denial_observed": mode == "attack" and impact_ok,
        "same_witness_recovered": recovery_ok,
        "checks": {
            "baseline_healthy": baseline_ok,
            "attacker_context_count": len(contexts),
            "withheld_request_count": withholding_count,
            "peak_concurrent_pre_auth_contexts": peak,
            "impact_failed_registrations": sum(service_failed(row) for row in phases["impact"]),
            "recovery_successes": sum(service_ok(row) for row in phases["recovery"]),
            "registration_limit_ms": limit,
            "crash_free": crash_free,
        },
    }


def write_manifest(run_dir: Path) -> None:
    attacker_map = load_object(run_dir / "attacker_map.json")
    attacker_logs = [row["log_file"] for row in attacker_map.get("attackers", [])]
    files = {name: sha256(run_dir / name) for name in (*INPUTS, *attacker_logs, "verdict.json")}
    output = run_dir / "evidence_manifest.json"
    if output.exists() or output.is_symlink():
        raise ValueError("기존 evidence manifest는 덮어쓰지 않습니다")
    output.write_text(json.dumps({"schema": "auth-timeout.evidence.v1", "files": files}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        run_dir = args.run_dir.resolve()
        verdict = verify(run_dir)
        output = run_dir / "verdict.json"
        if output.exists() or output.is_symlink():
            raise ValueError("기존 verdict는 덮어쓰지 않습니다")
        output.write_text(json.dumps(verdict, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(run_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"auth-timeout 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
