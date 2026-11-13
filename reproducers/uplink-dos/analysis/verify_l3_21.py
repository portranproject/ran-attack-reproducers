#!/usr/bin/env python3
"""정규화 입력을 실제 탐지 엔진에 재생해 L3-21 결과를 확인한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def regular(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"일반 파일이 아닙니다: {path}")
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()


def verify(run_dir: Path, detector: Path, config: Path) -> dict:
    run = json.loads(regular(run_dir / "run.json").read_text(encoding="utf-8"))
    mode = run.get("mode")
    if mode not in {"control", "emulation"}:
        raise ValueError("실행 mode가 잘못됐습니다")
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(
            [str(regular(detector)), "--replay", str(regular(run_dir / "detector-input.jsonl")), "--speed", "max", "--config", str(regular(config))],
            cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
    if result.returncode != 0:
        raise ValueError(f"탐지 엔진 재생 실패(rc={result.returncode}): {result.stderr.strip()}")
    raises = [line for line in result.stdout.splitlines() if line.startswith("ALERT RAISE rule=L3-21 ")]
    branch1 = [line for line in raises if " branch=1 " in line]
    passed = not raises if mode == "control" else len(raises) == 1 and len(branch1) == 1
    value = {"schema": "uplink-dos.l3-21-verdict.v1", "run_id": run.get("run_id"), "mode": mode,
             "passed": passed, "l3_21_raise_count": len(raises), "l3_21_branch1_raise_count": len(branch1),
             "detector_sha256": sha256(detector), "detector_config_sha256": sha256(config),
             "stdout": result.stdout.splitlines(), "stderr": result.stderr.splitlines()}
    output = run_dir / "l3-21-verdict.json"
    if output.exists() or output.is_symlink():
        raise ValueError("기존 L3-21 판정은 덮어쓰지 않습니다")
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("detector", type=Path)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    try:
        verdict = verify(args.run_dir.resolve(), args.detector.resolve(), args.config.resolve())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(f"L3-21 재생 판정 실패: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
