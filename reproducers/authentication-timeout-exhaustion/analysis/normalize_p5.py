#!/usr/bin/env python3
"""OCUDU/Open5GS p5 원문을 가입자별 pre-auth 컨텍스트로 정규화한다."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from .export_labels import load_object, regular
except ImportError:
    from export_labels import load_object, regular

TIME = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<clock>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d{1,9}))?(?P<zone>Z|[+-]\d{2}:?\d{2})?"
)
SUCI = re.compile(
    r"suci-[0-9]+-(?P<mcc>[0-9]{3})-(?P<mnc>[0-9]{2,3})-"
    r"[0-9]+-[0-9]+-[0-9]+-(?P<msin>[0-9]+)", re.I,
)
SUCI_IDENTITY = re.compile(r"\]\s+SUCI(?:\s+\(|\s*$)")
IDS = re.compile(r"RAN_UE_NGAP_ID\[(?P<ran>\d+)\]\s+AMF_UE_NGAP_ID\[(?P<amf>\d+)\]")
CU_SETUP = re.compile(r"ue=(?P<ue>\d+).*Rx SRB1 DCCH UL rrcSetupComplete")
CU_CREATED = re.compile(r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+): NGAP UE context created")
CU_INITIAL = re.compile(r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+): InitialUEMessage")
CU_BINDING = re.compile(r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+): Setting AMF-UE-NGAP-ID=(?P<amf>\d+)")
CU_REMOVED = re.compile(
    r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+)\s+amf_ue=(?P<amf>\d+): Removing NGAP UE context"
)
WITHHELD = "AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld"
SUBMITTED = "AUTH_TIMEOUT_EXHAUSTION event=authentication_response_submitted"


def attacker_groups(attackers: list[dict], log_count: int) -> list[list[dict]]:
    groups = [[] for _ in range(log_count)]
    for fallback, profile in enumerate(attackers):
        process_index = profile.get("process_index", fallback)
        if type(process_index) is not int or not 0 <= process_index < log_count:
            raise ValueError("공격자 process_index가 잘못됐습니다")
        groups[process_index].append(profile)
    if any(not group for group in groups):
        raise ValueError("비어 있는 공격자 프로세스가 있습니다")
    for group in groups:
        ue_ids = [row.get("ue_id", index) for index, row in enumerate(group)]
        if ue_ids != list(range(len(group))):
            raise ValueError("공격자 ue_id는 프로세스별 0부터 연속이어야 합니다")
    return groups


def realtime_ns(line: str) -> int | None:
    match = TIME.search(line)
    if not match:
        return None
    zone = match.group("zone") or "+00:00"
    if zone == "Z":
        zone = "+00:00"
    elif len(zone) == 5:
        zone = zone[:3] + ":" + zone[3:]
    parsed = datetime.fromisoformat(f"{match.group('date')}T{match.group('clock')}{zone}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    fraction = int((match.group("fraction") or "").ljust(9, "0"))
    return int(parsed.timestamp()) * 1_000_000_000 + fraction


def subscriber_fingerprint(line: str) -> str | None:
    match = SUCI.search(line)
    if not match:
        return None
    imsi = match.group("mcc") + match.group("mnc") + match.group("msin")
    return hashlib.sha256(imsi.encode()).hexdigest()


def parse_cu(text: str) -> dict[tuple[int, int], dict]:
    setup: dict[int, int] = {}
    contexts: dict[int, dict] = {}
    joined: dict[tuple[int, int], dict] = {}
    for line in text.splitlines():
        timestamp = realtime_ns(line)
        match = CU_SETUP.search(line)
        if match:
            setup[int(match.group("ue"))] = timestamp or 0
            continue
        match = CU_CREATED.search(line)
        if match:
            ue, ran = int(match.group("ue")), int(match.group("ran"))
            contexts[ran] = {"ue": ue, "created_realtime_ns": timestamp, "initial_ue_message": False}
            continue
        match = CU_INITIAL.search(line)
        if match:
            ran = int(match.group("ran"))
            if ran in contexts:
                contexts[ran]["initial_ue_message"] = True
            continue
        match = CU_BINDING.search(line)
        if match:
            ue, ran, amf = map(int, (match.group("ue"), match.group("ran"), match.group("amf")))
            context = contexts.get(ran)
            if context and context["ue"] == ue:
                context = dict(context)
                context["rrc_setup_complete"] = ue in setup
                joined[(ran, amf)] = context
            continue
        match = CU_REMOVED.search(line)
        if match:
            ran, amf = int(match.group("ran")), int(match.group("amf"))
            if (ran, amf) in joined:
                joined[(ran, amf)]["released_realtime_ns"] = timestamp
    return joined


def latest_unbound(contexts: list[dict]) -> dict | None:
    for context in reversed(contexts):
        if context.get("subscriber_fingerprint") is None:
            return context
    return None


def active_for(contexts: list[dict], fingerprint: str) -> dict | None:
    for context in reversed(contexts):
        if context.get("subscriber_fingerprint") == fingerprint and context.get("released_realtime_ns") is None:
            return context
    return None


def parse_amf(text: str) -> list[dict]:
    contexts: list[dict] = []
    pending_initial: dict | None = None
    pending_release: int | None = None
    for line in text.splitlines():
        timestamp = realtime_ns(line)
        if "InitialUEMessage" in line:
            pending_initial = {
                "created_realtime_ns": timestamp,
                "subscriber_fingerprint": None,
                "authentication_request_count": 0,
                "authentication_response_count": 0,
                "authentication_failure_count": 0,
                "released_realtime_ns": None,
            }
            contexts.append(pending_initial)
            continue
        if "UEContextReleaseCommand" in line or "Clear NG Context" in line:
            pending_release = timestamp
            continue
        ids = IDS.search(line)
        if ids:
            ran, amf = int(ids.group("ran")), int(ids.group("amf"))
            if pending_release is not None:
                matches = [row for row in contexts if row.get("ran_ue_ngap_id") == ran and row.get("amf_ue_ngap_id") == amf and row.get("released_realtime_ns") is None]
                if matches:
                    matches[-1]["released_realtime_ns"] = pending_release or timestamp
                pending_release = None
            elif pending_initial is not None and "ran_ue_ngap_id" not in pending_initial:
                pending_initial["ran_ue_ngap_id"] = ran
                pending_initial["amf_ue_ngap_id"] = amf
            continue

        fingerprint = subscriber_fingerprint(line)
        if fingerprint is None:
            continue
        if SUCI_IDENTITY.search(line):
            context = latest_unbound(contexts)
            if context is not None:
                context["subscriber_fingerprint"] = fingerprint
            continue
        context = active_for(contexts, fingerprint)
        if context is None:
            continue
        if "Authentication request" in line:
            context["authentication_request_count"] += 1
        elif "Authentication response" in line:
            context["authentication_response_count"] += 1
        elif "Authentication failure" in line:
            context["authentication_failure_count"] += 1
    return contexts


def normalize(run_dir: Path, attacker_logs: list[Path]) -> tuple[list[dict], list[dict]]:
    run_dir = run_dir.resolve()
    run = load_object(run_dir / "run.json")
    profiles = load_object(run_dir / "profiles.manifest.json")
    attackers = [row for row in profiles.get("profiles", []) if row.get("role") == "attacker"]
    if len(attackers) != run.get("attacker_count"):
        raise ValueError("공격자 profile 수가 run과 일치하지 않습니다")
    groups = attacker_groups(attackers, len(attacker_logs))
    if run.get("attacker_process_count", len(attacker_logs)) != len(attacker_logs):
        raise ValueError("공격자 프로세스 수와 UE 로그 수가 일치하지 않습니다")
    resolved_logs = [path.resolve() for path in attacker_logs]
    if len({path.name for path in resolved_logs}) != len(resolved_logs) or any(path.parent != run_dir for path in resolved_logs):
        raise ValueError("공격자 UE 로그는 run 디렉터리 안의 서로 다른 파일이어야 합니다")
    mode = run.get("mode")
    if mode not in {"control", "attack"}:
        raise ValueError("run mode가 잘못됐습니다")
    service_rows = [json.loads(line) for line in regular(run_dir / "service.jsonl").read_text().splitlines() if line]
    impact_times = [row.get("realtime_ns") for row in service_rows if row.get("phase") == "impact"]
    if len(impact_times) != 5 or any(type(value) is not int for value in impact_times):
        raise ValueError("impact 서비스 관측창이 잘못됐습니다")
    impact_end = max(impact_times)

    truth = []
    for group, path in zip(groups, resolved_logs, strict=True):
        text = regular(path).read_text(encoding="utf-8", errors="replace")
        for fallback, profile in enumerate(group):
            ue_id = profile.get("ue_id", fallback)
            withheld = text.count(f"{WITHHELD} ue={ue_id} ")
            submitted = text.count(f"{SUBMITTED} ue={ue_id} ")
            if mode == "attack" and (withheld < 1 or submitted != 0):
                raise ValueError(f"attack UE {ue_id} 마커가 잘못됐습니다: {path.name}")
            if mode == "control" and (withheld != 0 or submitted < 1):
                raise ValueError(f"control UE {ue_id} 마커가 잘못됐습니다: {path.name}")
            truth.append({
                "schema": "auth-timeout.truth.v1",
                "subscriber_fingerprint": profile["subscriber_fingerprint"],
                "withheld_request_count": withheld,
                "submitted_response_count": submitted,
                "response_submitted": submitted > 0,
            })

    cu = parse_cu(regular(run_dir / "cu.log").read_text(encoding="utf-8", errors="replace"))
    amf = parse_amf(regular(run_dir / "amf.log").read_text(encoding="utf-8", errors="replace"))
    expected = {row["subscriber_fingerprint"] for row in attackers}
    contexts = []
    for row in amf:
        if row.get("created_realtime_ns") is None or row["created_realtime_ns"] > impact_end:
            continue
        fingerprint = row.get("subscriber_fingerprint")
        if fingerprint not in expected:
            continue
        ids = (row.get("ran_ue_ngap_id"), row.get("amf_ue_ngap_id"))
        cu_row = cu.get(ids)
        if cu_row is None:
            raise ValueError(f"CU exact join이 없습니다: RAN/AMF ID {ids}")
        contexts.append({
            "schema": "auth-timeout.context.v1",
            "subscriber_fingerprint": fingerprint,
            "ran_ue_ngap_id": ids[0],
            "amf_ue_ngap_id": ids[1],
            "rrc_setup_complete": cu_row["rrc_setup_complete"],
            "initial_ue_message": cu_row["initial_ue_message"],
            "authentication_request": False,
            "authentication_request_observed_at": "ue_nas_handler",
            "authentication_request_count": row["authentication_request_count"],
            "authentication_response_count": row["authentication_response_count"],
            "authentication_failure_count": row["authentication_failure_count"],
            "created_realtime_ns": row["created_realtime_ns"],
            "released_realtime_ns": cu_row.get("released_realtime_ns", row["released_realtime_ns"]),
        })
    if {row["subscriber_fingerprint"] for row in contexts} != expected or len(contexts) < len(expected):
        raise ValueError("모든 공격 가입자의 컨텍스트가 조인되지 않았습니다")
    context_counts = {
        fingerprint: sum(row["subscriber_fingerprint"] == fingerprint for row in contexts)
        for fingerprint in expected
    }
    truth_by_fingerprint = {row["subscriber_fingerprint"]: row for row in truth}
    count_key = "withheld_request_count" if mode == "attack" else "submitted_response_count"
    if any(truth_by_fingerprint[fingerprint][count_key] < count for fingerprint, count in context_counts.items()):
        raise ValueError("UE 인증 요청 처리 마커와 AMF 컨텍스트 수가 일치하지 않습니다")
    for row in contexts:
        row["authentication_request"] = True
    return truth, contexts


def exclusive_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"기존 정규화 결과는 덮어쓰지 않습니다: {path.name}")
    with path.open("x", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def exclusive_json(path: Path, value: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError(f"기존 정규화 결과는 덮어쓰지 않습니다: {path.name}")
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--attacker-log", action="append", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_dir = args.run_dir.resolve()
        truth, contexts = normalize(run_dir, args.attacker_log)
        profiles = load_object(run_dir / "profiles.manifest.json")
        attackers = [row for row in profiles["profiles"] if row.get("role") == "attacker"]
        groups = attacker_groups(attackers, len(args.attacker_log))
        mapping = {
            "schema": "auth-timeout.attacker-map.v1",
            "attackers": [{
                "subscriber_fingerprint": profile["subscriber_fingerprint"],
                "log_file": path.name,
                "log_sha256": hashlib.sha256(regular(path).read_bytes()).hexdigest(),
            } for group, path in zip(groups, args.attacker_log, strict=True) for profile in group],
        }
        exclusive_json(run_dir / "attacker_map.json", mapping)
        exclusive_jsonl(run_dir / "attacker_truth.jsonl", truth)
        exclusive_jsonl(run_dir / "contexts.jsonl", contexts)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"p5 로그 정규화 실패: {error}", file=sys.stderr)
        return 2
    print(f"p5 로그 정규화: {len(contexts)}개 공격 컨텍스트 exact join")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
