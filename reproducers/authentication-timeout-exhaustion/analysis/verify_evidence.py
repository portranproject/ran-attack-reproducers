#!/usr/bin/env python3
"""봉인된 실행 원문의 SHA-256을 다시 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .export_labels import load_object, sha256
except ImportError:
    from export_labels import load_object, sha256


def verify(run_dir: Path) -> int:
    manifest = load_object(run_dir / "evidence_manifest.json")
    if manifest.get("schema") != "auth-timeout.evidence.v1" or not isinstance(manifest.get("files"), dict):
        raise ValueError("evidence manifest 스키마가 다릅니다")
    for name, expected in manifest["files"].items():
        if Path(name).name != name or sha256(run_dir / name) != expected:
            raise ValueError(f"원문 해시가 다릅니다: {name}")
    return len(manifest["files"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.run_dir.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"evidence 검증 실패: {error}", file=sys.stderr)
        return 2
    print(f"evidence 검증: {count}개 파일 일치")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
