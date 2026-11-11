#!/usr/bin/env python3
"""OAI 가입자 설정을 비밀값 없이 fingerprint manifest로 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

UICC = re.compile(r"(?m)^\s*uicc([0-9]+)\s*=\s*\{")
IMSI = re.compile(r"\bimsi\s*=\s*(?:[\"'])?([0-9]{15})(?:[\"'])?\s*;", re.I)


def regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"일반 파일이 아닙니다: {path}")
    return path.read_bytes()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def profiles(path: Path, role: str, process_index: int) -> list[dict]:
    data = regular(path)
    text = data.decode("utf-8")
    sections = list(UICC.finditer(text))
    if not sections:
        raise ValueError(f"uicc 설정이 없습니다: {path}")
    ids = [int(match.group(1)) for match in sections]
    if ids != list(range(len(ids))):
        raise ValueError(f"uicc 번호는 0부터 연속이어야 합니다: {path}")
    rows = []
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        matches = IMSI.findall(text[section.start():end])
        if len(matches) != 1:
            raise ValueError(f"uicc{index}의 IMSI가 정확히 하나여야 합니다: {path}")
        rows.append({
            "role": role,
            "process_index": process_index,
            "ue_id": index,
            "config_sha256": digest(data),
            "subscriber_fingerprint": digest(matches[0].encode()),
        })
    return rows


def build(attackers: list[Path], witness: Path) -> dict:
    attacker_rows = [
        row
        for process_index, path in enumerate(attackers)
        for row in profiles(path, "attacker", process_index)
    ]
    if len(attacker_rows) < 2:
        raise ValueError("자원 누적 실험에는 서로 다른 공격 가입자가 2개 이상 필요합니다")
    witness_rows = profiles(witness, "witness", 0)
    if len(witness_rows) != 1:
        raise ValueError("witness 설정에는 uicc0 하나만 있어야 합니다")
    rows = attacker_rows + witness_rows
    fingerprints = [row["subscriber_fingerprint"] for row in rows]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("공격자 또는 witness 가입자 IMSI가 중복됩니다")
    return {
        "schema": "auth-timeout.profiles.v1",
        "attacker_count": len(attacker_rows),
        "attacker_process_count": len(attackers),
        "profiles": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attacker", action="append", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.attacker, args.witness)
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("기존 manifest는 덮어쓰지 않습니다")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(args.output, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            output.write("\n")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        print(f"profile manifest 생성 실패: {error}", file=sys.stderr)
        return 2
    print(
        f"profile manifest: 공격자 {result['attacker_count']}명/"
        f"프로세스 {result['attacker_process_count']}개, witness 1명"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
