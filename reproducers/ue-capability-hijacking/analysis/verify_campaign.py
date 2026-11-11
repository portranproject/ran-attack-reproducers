#!/usr/bin/env python3
"""matched control→emulation 세 세트와 child 봉인을 검증한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from .verify_run import load_object, regular, sha256
except ImportError:
    from verify_run import load_object, regular, sha256


def verify_evidence(run_dir: Path) -> None:
    manifest = load_object(run_dir / "evidence_manifest.json")
    if manifest.get("schema") != "ue-capability.evidence.v1" or not isinstance(manifest.get("files"), dict):
        raise ValueError("evidence manifest가 잘못됐습니다")
    for name, expected in manifest["files"].items():
        path = regular(run_dir / name)
        if expected != {"size": path.stat().st_size, "sha256": sha256(path)}:
            raise ValueError(f"봉인 후 파일이 바뀌었습니다: {run_dir.name}/{name}")


def verify(root: Path, campaign: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,70}", campaign) or root.is_symlink() or not root.is_dir():
        raise ValueError("안전한 run root와 campaign id가 필요합니다")
    children = []
    for index in range(1, 4):
        pair = []
        for mode in ("control", "emulation"):
            run_id = f"{campaign}-{mode}-{index}"
            run_dir = root / run_id
            run = load_object(run_dir / "run.json")
            verdict = load_object(run_dir / "verdict.json")
            verify_evidence(run_dir)
            if run.get("schema") != "ue-capability.run.v1" or run.get("run_id") != run_id or run.get("mode") != mode:
                raise ValueError(f"child run identity가 다릅니다: {run_id}")
            if verdict.get("schema") != "ue-capability.verdict.v1" or verdict.get("passed") is not True:
                raise ValueError(f"child verdict가 통과하지 않았습니다: {run_id}")
            if mode == "control" and verdict.get("control_healthy") is not True:
                raise ValueError(f"control 판정이 잘못됐습니다: {run_id}")
            if mode == "emulation" and verdict.get("pre_security_injection_observed") is not True:
                raise ValueError(f"emulation 기전이 불완전합니다: {run_id}")
            if any(verdict.get(key) is not False for key in ("mitm_relay_observed", "capability_content_modified", "capability_downgrade_accepted")):
                raise ValueError(f"주장 경계가 잘못됐습니다: {run_id}")
            pair.append(run)
            children.append({"run_id": run_id, "set_index": index, "mode": mode, "checks": verdict["checks"]})
        for key in ("source_commit", "ue_patch_sha256", "ue_binary_sha256", "gnb_config_sha256", "core_config_sha256", "ue_config_sha256"):
            if pair[0].get(key) != pair[1].get(key):
                raise ValueError(f"set {index}의 matched 조건이 다릅니다: {key}")
    return {
        "schema": "ue-capability.campaign.v1",
        "campaign_id": campaign,
        "matched_repetitions": 3,
        "set_order": ["control", "emulation"],
        "passed": True,
        "mitm_relay_observed": False,
        "capability_content_modified": False,
        "capability_downgrade_accepted": False,
        "children": children,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("campaign_id")
    args = parser.parse_args()
    try:
        result = verify(args.run_root.resolve(), args.campaign_id)
        output = args.run_root / f"{args.campaign_id}-campaign.json"
        if output.exists() or output.is_symlink():
            raise ValueError("기존 campaign 결과는 덮어쓰지 않습니다")
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ue-capability campaign 판정 실패: {error}", file=sys.stderr)
        return 2
    print(f"ue-capability campaign: matched control→emulation 3/3 통과 ({output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
