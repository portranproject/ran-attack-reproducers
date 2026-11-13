#!/usr/bin/env python3
"""p5 F1 실측과 같은 연결별 등록 거절 신호를 L3-21 입력으로 만든다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_MS = 1_794_387_044_000
COUNTERS = {
    "RRC.ConnEstabAtt": {"total": 0},
    "RRC.ConnEstabSucc": {"total": 0},
    "RRC.ConnEstabFailCause": {"NetworkReject": 0, "NoReply": 0, "Other": 0},
}


def generate(mode: str, session: str, output: Path) -> None:
    if mode not in {"control", "emulation"} or output.is_symlink() or not output.is_dir():
        raise ValueError("mode 또는 출력 디렉터리가 잘못됐습니다")
    count = 1 if mode == "control" else 5
    events = []
    frame = 1
    for index in range(count):
        start = BASE_MS + index * 500
        du_id, crnti = index, 0x4601 + index
        for offset, direction, proto, message, cause in (
            (0, "UL", "RRC", "RRCSetupRequest", None),
            (5, "DL", "RRC", "RRCSetup", None),
            (90, "UL", "RRC", "RRCSetupComplete", None),
            (90, "UL", "NAS", "RegistrationRequest", None),
            (100, "DL", "NAS", "RegistrationReject", 7),
        ):
            events.append({"frame": frame, "t_ms": start + offset, "du_id": du_id, "cu_id": du_id,
                           "crnti": crnti, "dir": direction, "proto": proto, "msg": message, "cause": cause})
            frame += 1

    observations = output / "observations.jsonl"
    detector_input = output / "detector-input.jsonl"
    if observations.exists() or observations.is_symlink() or detector_input.exists() or detector_input.is_symlink():
        raise ValueError("기존 출력은 덮어쓰지 않습니다")
    with observations.open("x", encoding="utf-8") as target:
        for order, row in enumerate(events):
            target.write(json.dumps({
                "schema": "uplink-dos.registration-failure-observation.v1", "order": order, "frame": row["frame"],
                "realtime_ns": row["t_ms"] * 1_000_000, "direction": row["dir"], "protocol": row["proto"],
                "message": row["msg"], "gnb_du_ue_f1ap_id": row["du_id"], "gnb_cu_ue_f1ap_id": row["cu_id"],
                "crnti": row["crnti"], "cause": row["cause"], "source": "detector-input-emulation",
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
    event_index = 0
    stop = events[-1]["t_ms"] + 5200
    for window_start in range(BASE_MS, stop, 100):
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
    parser.add_argument("mode", choices=("control", "emulation"))
    parser.add_argument("session")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        generate(args.mode, args.session, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
