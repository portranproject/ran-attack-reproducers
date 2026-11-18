#!/usr/bin/env python3
"""가입자 설정을 공유 virtual RU용 private runtime 파일로 복사한다."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def generate(source: Path, target: Path, count: int) -> None:
    if source.is_symlink() or not source.is_file() or target.exists() or target.is_symlink():
        raise ValueError("입력은 일반 파일이고 출력은 새 파일이어야 합니다")
    if count < 1 or count > 10:
        raise ValueError("UE 수는 1..10이어야 합니다")
    text = source.read_text(encoding="utf-8")
    if re.search(r"(?m)^\s*(RUs|cells)\s*=", text):
        raise ValueError("가입자 설정에 기존 RUs/cells가 있습니다")
    if len(re.findall(r"(?m)^\s*uicc\d+\s*=", text)) < count:
        raise ValueError("요청 수만큼 UICC 설정이 없습니다")
    target.write_text(text, encoding="utf-8")
    os.chmod(target, 0o600)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: multi_ru_config.py SOURCE TARGET COUNT", file=sys.stderr)
        return 2
    try:
        generate(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]))
    except (OSError, ValueError) as error:
        print(f"다중 RU 설정 생성 실패: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
