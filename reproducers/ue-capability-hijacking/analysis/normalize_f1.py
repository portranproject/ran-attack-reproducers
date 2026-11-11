#!/usr/bin/env python3
"""tshark F1 TSV를 detector 입력과 분리된 UE oracle로 정규화한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


FIELDS = {
    "rrc_setup_complete": "RRCSetupComplete",
    "security_mode_command": "SecurityModeCommand",
    "security_mode_complete": "SecurityModeComplete",
    "ue_capability_enquiry": "UECapabilityEnquiry",
    "ue_capability_information": "UECapabilityInformation",
}


def parse_id(value: str) -> int:
    value = value.split(",", 1)[0].strip()
    return int(value, 0)


def normalize(raw: Path, cu_ip: str, du_ip: str, output: Path) -> None:
    if raw.is_symlink() or not raw.is_file() or output.is_symlink():
        raise ValueError("입출력은 일반 파일·디렉터리여야 합니다")
    groups: dict[tuple[int, int], list[dict]] = defaultdict(list)
    with raw.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            present = [message for field, message in FIELDS.items() if row.get(field, "").strip()]
            if not present:
                continue
            if row.get("src") == du_ip and row.get("dst") == cu_ip:
                direction = "uplink"
            elif row.get("src") == cu_ip and row.get("dst") == du_ip:
                direction = "downlink"
            else:
                continue
            try:
                context = (parse_id(row["du_id"]), parse_id(row["cu_id"]))
                realtime_ns = int(float(row["time_epoch"]) * 1_000_000_000)
                frame = int(row["frame"])
            except (KeyError, TypeError, ValueError):
                continue
            for message in present:
                groups[context].append({"frame": frame, "realtime_ns": realtime_ns, "direction": direction, "message": message})

    candidates = [key for key, rows in groups.items() if any(row["message"] == "UECapabilityInformation" for row in rows)]
    if not candidates:
        candidates = [key for key, rows in groups.items() if any(row["message"] == "RRCSetupComplete" for row in rows)]
    if len(candidates) != 1:
        raise ValueError(f"대상 F1 UE context가 하나여야 합니다: {len(candidates)}")
    du_id, cu_id = candidates[0]
    rows = sorted(groups[(du_id, cu_id)], key=lambda row: (row["realtime_ns"], row["frame"], row["message"]))
    security_active = False
    observations = []
    seen = set()
    for row in rows:
        identity = (row["frame"], row["message"])
        if identity in seen:
            continue
        seen.add(identity)
        observations.append({
            "schema": "ue-capability.observation.v1",
            "order": len(observations),
            "source": "f1ap",
            "direction": row["direction"],
            "message": row["message"],
            "gnb_cu_ue_f1ap_id": cu_id,
            "gnb_du_ue_f1ap_id": du_id,
            "realtime_ns": row["realtime_ns"],
            "rrc_security_before": "ON" if security_active else "OFF",
        })
        if row["message"] == "SecurityModeComplete":
            security_active = True

    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (output / "observations.jsonl").open("x", encoding="utf-8") as target:
        for row in observations:
            target.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("cu_ip")
    parser.add_argument("du_ip")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        normalize(args.raw, args.cu_ip, args.du_ip, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
