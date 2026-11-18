#!/usr/bin/env python3
"""가입자 설정에 p5 단일 셀용 독립 virtual RU와 ZMQ endpoint를 추가한다."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def generate(source: Path, target: Path, count: int, endpoint_offset: int = 0) -> None:
    if source.is_symlink() or not source.is_file() or target.exists() or target.is_symlink():
        raise ValueError("입력은 일반 파일이고 출력은 새 파일이어야 합니다")
    if count < 1 or count > 10 or endpoint_offset < 0 or endpoint_offset + count > 15:
        raise ValueError("RU 수는 1..10이고 마지막 endpoint는 15 이하여야 합니다")
    text = source.read_text(encoding="utf-8")
    if re.search(r"(?m)^\s*(RUs|cells|zmq)\s*=", text):
        raise ValueError("가입자 설정에 기존 RUs/cells/zmq가 있습니다")
    if len(re.findall(r"(?m)^\s*uicc\d+\s*=", text)) < count:
        raise ValueError("요청 수만큼 UICC 설정이 없습니다")
    radios = ",\n".join(
        '  { nb_tx = 1; nb_rx = 1; sdr_addrs = "type=zmq"; }' for _ in range(count)
    )
    cells = ",\n".join(
        f"  {{ ru_id = {index}; band = 78; rf_freq = 3489420000L; rf_offset = 0L; "
        "numerology = 1; N_RB_DL = 51; ssb_start = 516; }"
        for index in range(count)
    )
    zmq = ",\n".join(
        f'  {{ tx_channels = ("tcp://127.0.0.1:{2001 + 100 * (endpoint_offset + index + 1)}"); '
        f'rx_channels = ("tcp://127.0.0.1:{2000 + 100 * (endpoint_offset + index + 1)}"); }}'
        for index in range(count)
    )
    target.write_text(
        text.rstrip()
        + f"\n\nRUs = (\n{radios}\n);\n\ncells = (\n{cells}\n);\n\nzmq = (\n{zmq}\n);\n",
        encoding="utf-8",
    )
    os.chmod(target, 0o600)


def main() -> int:
    if len(sys.argv) not in (4, 5):
        print("usage: multi_ru_config.py SOURCE TARGET COUNT [ENDPOINT_OFFSET]", file=sys.stderr)
        return 2
    try:
        generate(
            Path(sys.argv[1]),
            Path(sys.argv[2]),
            int(sys.argv[3]),
            int(sys.argv[4]) if len(sys.argv) == 5 else 0,
        )
    except (OSError, ValueError) as error:
        print(f"다중 RU 설정 생성 실패: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
