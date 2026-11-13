#!/usr/bin/env python3
"""F1 PCAP의 실제 RRC/NAS 순서를 L3-21 재생 입력으로 정규화한다."""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal
from pathlib import Path


RRC_FIELDS = (
    ("rrc_setup_request", "RRCSetupRequest", "UL"),
    ("rrc_setup", "RRCSetup", "DL"),
    ("rrc_setup_complete", "RRCSetupComplete", "UL"),
)
NAS_MESSAGES = {"0x41": ("RegistrationRequest", "UL"), "0x42": ("RegistrationAccept", "DL"), "0x44": ("RegistrationReject", "DL")}
COUNTERS = {
    "RRC.ConnEstabAtt": {"total": 0},
    "RRC.ConnEstabSucc": {"total": 0},
    "RRC.ConnEstabFailCause": {"NetworkReject": 0, "NoReply": 0, "Other": 0},
}


def parse_id(value: str) -> int:
    return int(value.split(",", 1)[0].strip(), 0)


def present(value: str) -> bool:
    return bool(value and value.strip())


def normalize(raw: Path, cu_ip: str, du_ip: str, session: str, output: Path) -> None:
    if raw.is_symlink() or not raw.is_file() or output.is_symlink() or not output.is_dir():
        raise ValueError("입력은 일반 파일, 출력은 실제 디렉터리여야 합니다")
    captured = []
    with raw.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source, delimiter="\t"):
            if row.get("src") == du_ip and row.get("dst") == cu_ip:
                direction = "UL"
            elif row.get("src") == cu_ip and row.get("dst") == du_ip:
                direction = "DL"
            else:
                continue
            try:
                frame = int(row["frame"])
                t_ms = int(Decimal(row["time_epoch"]) * 1000)
                du_id = parse_id(row["du_id"])
                cu_id = parse_id(row["cu_id"]) if present(row.get("cu_id", "")) else None
                crnti = parse_id(row["crnti"]) if present(row.get("crnti", "")) else None
            except (KeyError, ValueError):
                continue
            messages = [(name, "RRC", expected, None) for field, name, expected in RRC_FIELDS if present(row.get(field, ""))]
            nas_type = row.get("nas_type", "").split(",", 1)[0].strip().lower()
            if nas_type in NAS_MESSAGES:
                name, expected = NAS_MESSAGES[nas_type]
                cause = parse_id(row["nas_cause"]) if name == "RegistrationReject" and present(row.get("nas_cause", "")) else None
                messages.append((name, "NAS", expected, cause))
            for order, (name, proto, expected, cause) in enumerate(messages):
                if direction == expected:
                    captured.append({"frame": frame, "order": order, "t_ms": t_ms, "du_id": du_id, "cu_id": cu_id,
                                     "crnti": crnti, "dir": direction, "proto": proto, "msg": name, "cause": cause})

    captured.sort(key=lambda row: (row["t_ms"], row["frame"], row["order"]))
    crnti_by_du: dict[int, int] = {}
    events = []
    seen = set()
    for row in captured:
        identity = (row["frame"], row["msg"])
        if identity in seen:
            continue
        seen.add(identity)
        if row["crnti"] is not None:
            crnti_by_du[row["du_id"]] = row["crnti"]
        if row["du_id"] not in crnti_by_du:
            continue
        row["crnti"] = crnti_by_du[row["du_id"]]
        events.append(row)
    rejects = [row for row in events if row["msg"] == "RegistrationReject"]
    if not events or not rejects:
        raise ValueError("F1에서 RRC 연결과 RegistrationReject를 찾지 못했습니다")

    observations = output / "observations.jsonl"
    detector_input = output / "detector-input.jsonl"
    if observations.exists() or observations.is_symlink() or detector_input.exists() or detector_input.is_symlink():
        raise ValueError("기존 정규화 결과는 덮어쓰지 않습니다")
    with observations.open("x", encoding="utf-8") as target:
        for index, row in enumerate(events):
            target.write(json.dumps({
                "schema": "uplink-dos.registration-failure-observation.v1", "order": index, "frame": row["frame"],
                "realtime_ns": row["t_ms"] * 1_000_000, "direction": row["dir"], "protocol": row["proto"],
                "message": row["msg"], "gnb_du_ue_f1ap_id": row["du_id"], "gnb_cu_ue_f1ap_id": row["cu_id"],
                "crnti": row["crnti"], "cause": row["cause"], "source": "f1ap",
            }, sort_keys=True, separators=(",", ":")) + "\n")

    seq = 0
    lines = []
    def add(value: dict) -> None:
        nonlocal seq
        seq += 1
        value.update({"ver": 1, "session": session, "seq": seq})
        lines.append(value)
    add({"type": "hello", "cells": [{"cell_id": 1, "max_conn": None}], "period_ms": 100,
         "noreply_timeout_ms": 1000, "clock": "realtime", "ue_evt": True})
    start = events[0]["t_ms"] // 100 * 100
    stop = max(row["t_ms"] for row in rejects) + 5200
    event_index = 0
    for window_start in range(start, stop, 100):
        while event_index < len(events) and events[event_index]["t_ms"] < window_start + 100:
            row = events[event_index]
            value = {"type": "ue_evt", "t_ms": row["t_ms"], "cell_id": 1, "du_ue_id": row["du_id"],
                     "crnti": row["crnti"], "dir": row["dir"], "proto": row["proto"], "msg": row["msg"]}
            if row["proto"] == "NAS":
                value.update({"via": "F1", "sht": 0})
            if row["msg"] == "RRCSetupRequest":
                value["f"] = {"ue_identity": {"type": "randomValue"}}
            elif row["msg"] == "RegistrationRequest":
                value["f"] = {"reg_type": "initial", "id_type": "SUCI"}
            elif row["cause"] is not None:
                value["f"] = {"cause": row["cause"]}
            add(value)
            event_index += 1
        add({"type": "kpm2", "cell_id": 1, "t_start_ms": window_start, "t_end_ms": window_start + 100,
             "cc": COUNTERS, "ue_evt_lost": []})
    with detector_input.open("x", encoding="utf-8") as target:
        for line in lines:
            target.write(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw", type=Path)
    parser.add_argument("cu_ip")
    parser.add_argument("du_ip")
    parser.add_argument("session")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        normalize(args.raw, args.cu_ip, args.du_ip, args.session, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
