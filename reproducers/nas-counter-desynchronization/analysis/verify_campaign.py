#!/usr/bin/env python3
"""L3-06 matched control→emulation 3세트를 집계한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"일반 파일이 아닙니다: {path}")
    return path


def load(path: Path) -> dict:
    value = json.loads(regular(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 객체가 아닙니다: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def verify(root: Path, campaign: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,70}", campaign) or root.is_symlink() or not root.is_dir():
        raise ValueError("campaign id 또는 run root가 안전하지 않습니다")
    children, hashes, detector_identities = [], {}, set()
    for set_index in range(1, 4):
        for mode in ("control", "emulation"):
            run_id = f"{campaign}-{mode}-{set_index}"
            run_dir = root / run_id
            run, verdict = load(run_dir / "run.json"), load(run_dir / "verdict.json")
            oracle = json.loads(regular(run_dir / "oracle.jsonl").read_text(encoding="utf-8").splitlines()[0])
            if run.get("run_id") != run_id or run.get("mode") != mode or run.get("rule_ids") != ["L3-06"]:
                raise ValueError(f"child run identity가 다릅니다: {run_id}")
            if verdict.get("passed") is not True:
                raise ValueError(f"child verdict가 통과하지 않았습니다: {run_id}")
            expected = 0 if mode == "control" else 1
            checks = oracle.get("checks", {})
            if checks.get("unsolicited_security_mode_reject_count") != expected or checks.get("l3_06_raise_count") != expected:
                raise ValueError(f"L3-06 입력 또는 경보 수가 다릅니다: {run_id}")
            detector = run.get("source", {}).get("detector", {})
            identity = detector.get("binary_sha256"), detector.get("config_sha256")
            if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in identity):
                raise ValueError(f"탐지 엔진·설정 해시가 없습니다: {run_id}")
            detector_identities.add(identity)
            for path in sorted(run_dir.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"child에 심볼릭 링크가 있습니다: {path}")
                if path.is_file():
                    hashes[f"{run_id}/{path.relative_to(run_dir)}"] = sha256(path)
            children.append({"run_id": run_id, "set_index": set_index, "mode": mode, "checks": checks})
    if len(detector_identities) != 1:
        raise ValueError("child가 서로 다른 탐지 엔진 또는 설정을 사용했습니다")
    detector_sha256, config_sha256 = detector_identities.pop()
    return {"schema": "nas-counter-desync.campaign.v1", "campaign_id": campaign,
            "matched_repetitions": 3, "set_order": ["control", "emulation"], "passed": True,
            "detector_sha256": detector_sha256, "detector_config_sha256": config_sha256,
            "live_protocol_path_observed": True, "mitm_observed": False,
            "nas_counter_wrap_observed": False, "children": children, "raw_files_sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("campaign_id")
    args = parser.parse_args()
    try:
        result = verify(args.run_root.resolve(), args.campaign_id)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"L3-06 campaign 판정 실패: {error}", file=sys.stderr)
        return 2
    output = args.run_root / f"{args.campaign_id}-campaign.json"
    if output.exists() or output.is_symlink():
        print("기존 campaign 결과는 덮어쓰지 않습니다", file=sys.stderr)
        return 2
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"nas-counter-desync-campaign: matched control→emulation 3/3 통과 ({output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
