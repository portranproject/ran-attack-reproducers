#!/usr/bin/env python3
"""matched control→attack 3세트와 각 원문 봉인을 검증한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from .export_labels import load_object, sha256
    from .verify_evidence import verify as verify_evidence
except ImportError:
    from export_labels import load_object, sha256
    from verify_evidence import verify as verify_evidence


def verify(root: Path, campaign: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", campaign):
        raise ValueError("안전한 campaign id가 아닙니다")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("run root가 실제 디렉터리가 아닙니다")

    children = []
    for index in range(1, 4):
        pair = []
        for mode in ("control", "attack"):
            run_id = f"{campaign}-{mode}-{index}"
            run_dir = root / run_id
            run = load_object(run_dir / "run.json")
            verdict = load_object(run_dir / "verdict.json")
            verify_evidence(run_dir)
            if run.get("schema") != "auth-timeout.run.v1" or run.get("run_id") != run_id or run.get("mode") != mode:
                raise ValueError(f"child run identity가 다릅니다: {run_id}")
            if verdict.get("schema") != "auth-timeout.verdict.v1" or verdict.get("run_id") != run_id or verdict.get("mode") != mode or verdict.get("passed") is not True:
                raise ValueError(f"child verdict가 통과하지 않았습니다: {run_id}")
            if verdict.get("same_witness_recovered") is not True:
                raise ValueError(f"같은 witness가 회복하지 않았습니다: {run_id}")
            if mode == "control":
                if any(verdict.get(key) is not False for key in ("mechanism_reproduced", "resource_accumulation_observed", "witness_denial_observed")):
                    raise ValueError(f"control에 공격 효과가 있습니다: {run_id}")
            elif not all(verdict.get(key) is True for key in ("mechanism_reproduced", "resource_accumulation_observed", "witness_denial_observed")):
                raise ValueError(f"attack 효과가 불완전합니다: {run_id}")
            pair.append(run)
            children.append({"run_id": run_id, "set_index": index, "mode": mode, "checks": verdict["checks"]})

        matched = (
            "attacker_count", "start_interval_ms",
            "profile_manifest_sha256", "gnb_config_sha256", "core_config_sha256",
            "phase_driver_sha256", "ue_patch_sha256", "ru_sharing_patch_sha256", "ue_binary_sha256", "zmq_library_sha256", "runtime_config_sha256",
        )
        for key in matched:
            if pair[0].get(key) != pair[1].get(key):
                raise ValueError(f"set {index}의 matched 조건이 다릅니다: {key}")
        control_phase = root / f"{campaign}-control-{index}" / "phase_inputs.json"
        attack_phase = root / f"{campaign}-attack-{index}" / "phase_inputs.json"
        if sha256(control_phase) != sha256(attack_phase):
            raise ValueError(f"set {index}의 phase input이 다릅니다")
        control_service = [json.loads(line) for line in (root / f"{campaign}-control-{index}" / "service.jsonl").read_text().splitlines()]
        elapsed = [row.get("elapsed_ms") for row in control_service]
        if not elapsed or any(type(value) is not int or value < 0 for value in elapsed):
            raise ValueError(f"set {index}의 control 서비스 지연 표본이 잘못됐습니다")
        expected_limit = max(10_000, max(elapsed) * 3)
        if pair[1].get("registration_limit_ms") != expected_limit:
            raise ValueError(f"set {index}의 attack 등록 제한이 control에서 사전 고정되지 않았습니다")

    return {
        "schema": "auth-timeout.campaign.v1",
        "campaign_id": campaign,
        "matched_repetitions": 3,
        "set_order": ["control", "attack"],
        "passed": True,
        "children": children,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("campaign_id")
    args = parser.parse_args()
    try:
        result = verify(args.run_root.resolve(), args.campaign_id)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"auth-timeout campaign 판정 실패: {error}", file=sys.stderr)
        return 2
    output = args.run_root / f"{args.campaign_id}-campaign.json"
    if output.exists() or output.is_symlink():
        print("기존 campaign 결과는 덮어쓰지 않습니다", file=sys.stderr)
        return 2
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"auth-timeout campaign: matched control→attack 3/3 통과 ({output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
