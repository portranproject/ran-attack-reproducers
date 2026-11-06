#!/usr/bin/env python3
"""세 번의 matched control→emulation 실행과 원문 해시를 집계한다."""

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
    digest = hashlib.sha256()
    with regular(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(root: Path, campaign: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}", campaign):
        raise ValueError("안전한 campaign id가 아닙니다")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("run root가 실제 디렉터리가 아닙니다")

    children = []
    raw_hashes = {}
    for set_index in range(1, 4):
        for mode in ("control", "emulation"):
            run_id = f"{campaign}-{mode}-{set_index}"
            run_dir = root / run_id
            run = load(run_dir / "run.json")
            verdict = load(run_dir / "verdict.json")
            if run.get("schema") != "uplink-dos.run.v1" or run.get("run_id") != run_id or run.get("mode") != mode:
                raise ValueError(f"child run identity가 다릅니다: {run_id}")
            if verdict.get("schema") != "uplink-dos.verdict.v1" or verdict.get("run_id") != run_id or verdict.get("mode") != mode or verdict.get("passed") is not True:
                raise ValueError(f"child verdict가 통과하지 않았습니다: {run_id}")
            if verdict.get("rf_overshadowing_observed") is not False or verdict.get("same_victim_recovered") is not True:
                raise ValueError(f"주장 경계 또는 동일 UE 회복이 잘못됐습니다: {run_id}")
            if mode == "control":
                if verdict.get("protocol_impact_reproduced") is not False or verdict["checks"].get("service_request_substitution_count") != 0:
                    raise ValueError(f"control에 변조가 있습니다: {run_id}")
            elif not all(verdict.get(key) is True for key in (
                "protocol_impact_reproduced", "network_effect_observed", "victim_service_loss_observed"
            )):
                raise ValueError(f"emulation 효과가 불완전합니다: {run_id}")

            files = {}
            for path in sorted(run_dir.iterdir()):
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"child에 비정규 항목이 있습니다: {path}")
                files[path.name] = sha256(path)
                raw_hashes[f"{run_id}/{path.name}"] = files[path.name]
            children.append({
                "run_id": run_id,
                "set_index": set_index,
                "mode": mode,
                "victim_pid": run.get("victim_pid"),
                "verdict_sha256": files["verdict.json"],
                "checks": verdict["checks"],
            })

    return {
        "schema": "uplink-dos.campaign.v1",
        "campaign_id": campaign,
        "matched_repetitions": 3,
        "set_order": ["control", "emulation"],
        "passed": True,
        "rf_overshadowing_observed": False,
        "children": children,
        "raw_files_sha256": raw_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("campaign_id")
    args = parser.parse_args()
    try:
        result = verify(args.run_root.resolve(), args.campaign_id)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"uplink campaign 판정 실패: {error}", file=sys.stderr)
        return 2
    output = args.run_root / f"{args.campaign_id}-campaign.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"uplink-campaign: matched control→emulation 3/3 통과 ({output})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
