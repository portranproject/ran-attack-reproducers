#!/usr/bin/env python3
"""공격 1.0 자격 범위 밖인 6개 AN 룰의 독립적인 탐지 입력을 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


BASE_MS = 1_794_387_044_000
PERIOD_MS = 100
CELL_ID = 1
COUNTERS = {
    "RRC.ConnEstabAtt": {"total": 0},
    "RRC.ConnEstabSucc": {"total": 0},
    "RRC.ConnEstabFailCause": {"NetworkReject": 0, "NoReply": 0, "Other": 0},
}
STMSI_SHORT = "0x00000a0b0c0d"
STMSI_MOB = [f"0x0000b000000{index}" for index in range(1, 6)]


@dataclass
class Signal:
    session: str
    node_id: str
    duration_ms: int
    events: list[tuple[int, int, dict[str, Any]]] = field(default_factory=list)
    _order: int = 0

    def add(
        self,
        offset_ms: int,
        du: int,
        direction: str,
        protocol: str,
        message: str,
        *,
        fields: dict[str, Any] | None = None,
        sht: int | None = None,
        via: str | None = None,
    ) -> None:
        self._order += 1
        row: dict[str, Any] = {
            "type": "ue_evt",
            "t_ms": BASE_MS + offset_ms,
            "cell_id": CELL_ID,
            "du_ue_id": du,
            "cu_ue_id": du,
            "crnti": 10_000 + du,
            "dir": direction,
            "proto": protocol,
            "msg": message,
        }
        if fields is not None:
            row["f"] = fields
        if protocol == "NAS":
            row["via"] = via or "F1"
            row["sht"] = 0 if sht is None else sht
        elif via is not None:
            row["via"] = via
        self.events.append((offset_ms, self._order, row))

    def setup_head(self, start: int, du: int, *, stmsi: str | None = None, random: bool = True) -> None:
        identity = {"type": "randomValue"} if random else {
            "type": "ng-5G-S-TMSI-Part1",
            "value": part1(stmsi or STMSI_SHORT),
        }
        self.add(start, du, "UL", "RRC", "RRCSetupRequest", fields={"est_cause": "mo-Signalling", "ue_identity": identity})
        self.add(start, du, "DL", "RRC", "RRCSetup")

    def normal_flow(
        self,
        start: int,
        du: int,
        *,
        identity_request: bool = False,
        assigned_stmsi: str | None = None,
        registration_stmsi: str | None = None,
        release_at: int | None = 1_000,
    ) -> None:
        self.setup_head(start, du, stmsi=registration_stmsi, random=registration_stmsi is None)
        self.add(start + 91, du, "UL", "RRC", "RRCSetupComplete")
        registration = {"reg_type": "initial", "id_type": "SUCI"}
        if registration_stmsi is not None:
            registration = {"reg_type": "mobility", "id_type": "5G-GUTI", "s_tmsi": registration_stmsi}
        self.add(start + 91, du, "UL", "NAS", "RegistrationRequest", fields=registration)
        if identity_request:
            self.add(start + 95, du, "DL", "NAS", "IdentityRequest")
            self.add(start + 100, du, "UL", "NAS", "IdentityResponse")
        self.add(start + 105, du, "DL", "NAS", "AuthenticationRequest")
        self.add(start + 118, du, "UL", "NAS", "AuthenticationResponse")
        self.add(start + 125, du, "DL", "NAS", "SecurityModeCommand", sht=3, fields={"cipher": "5G-EA0", "integrity": "5G-IA2"})
        self.add(start + 131, du, "UL", "NAS", "SecurityModeComplete", sht=4)
        self.add(start + 140, du, "DL", "RRC", "SecurityModeCommand", fields={"cipher": "nea0", "integrity": "nia2"})
        self.add(start + 150, du, "UL", "RRC", "SecurityModeComplete")
        self.add(start + 160, du, "DL", "RRC", "UECapabilityEnquiry")
        self.add(start + 175, du, "UL", "RRC", "UECapabilityInformation")
        accept_fields = {"s_tmsi": assigned_stmsi} if assigned_stmsi else None
        self.add(start + 190, du, "DL", "NAS", "RegistrationAccept", fields=accept_fields)
        self.add(start + 200, du, "UL", "NAS", "RegistrationComplete")
        if release_at is not None:
            self.release(start + release_at, du)

    def release(self, offset_ms: int, du: int) -> None:
        self.add(offset_ms, du, "DL", "F1AP", "UEContextReleaseCommand", fields={"cause": "radioNetwork:normal-release"})
        self.add(offset_ms, du, "UL", "F1AP", "UEContextReleaseComplete")

    def write(self, output: Path) -> None:
        if output.exists() or output.is_symlink():
            raise ValueError(f"기존 출력은 덮어쓰지 않습니다: {output}")
        ordered = sorted(self.events, key=lambda item: (item[0], item[1]))
        cursor = 0
        seq = 0

        def emit(target, value: dict[str, Any]) -> None:
            nonlocal seq
            seq += 1
            row = dict(value)
            row.update({"ver": 1, "session": self.session, "seq": seq})
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

        with output.open("x", encoding="utf-8") as target:
            emit(target, {
                "type": "hello",
                "producer": "ran-attack-reproducers",
                "node_id": self.node_id,
                "ue_evt": True,
                "cells": [{"cell_id": CELL_ID, "max_conn": None}],
                "period_ms": PERIOD_MS,
                "noreply_timeout_ms": 1_000,
                "si_sample_ms": 100,
                "clock": "realtime",
            })
            for window_start in range(0, self.duration_ms, PERIOD_MS):
                while cursor < len(ordered) and ordered[cursor][0] < window_start + PERIOD_MS:
                    emit(target, ordered[cursor][2])
                    cursor += 1
                emit(target, {
                    "type": "kpm2",
                    "cell_id": CELL_ID,
                    "t_start_ms": BASE_MS + window_start,
                    "t_end_ms": BASE_MS + window_start + PERIOD_MS,
                    "cc": COUNTERS,
                    "ue_evt_lost": [],
                })
        if cursor != len(ordered):
            output.unlink(missing_ok=True)
            raise ValueError("duration 안에 들어오지 않은 이벤트가 있습니다")


def part1(stmsi: str) -> str:
    return f"0x{int(stmsi, 16) & ((1 << 39) - 1):010x}"


def normal_control(session: str, node: str, duration: int = 3_000) -> Signal:
    signal = Signal(session, node, duration)
    signal.normal_flow(1_000, 3)
    return signal


def an_01(mode: str, session: str) -> Signal:
    if mode == "control":
        return normal_control(session, "an-01")
    signal = Signal(session, "an-01", 3_000)
    signal.setup_head(1_000, 3)
    signal.add(1_091, 3, "UL", "RRC", "RRCSetupComplete")
    signal.add(1_091, 3, "UL", "NAS", "RegistrationRequest", fields={"reg_type": "initial", "id_type": "SUCI"})
    signal.add(1_105, 3, "DL", "NAS", "AuthenticationRequest")
    signal.add(1_118, 3, "UL", "NAS", "AuthenticationFailure", fields={"cause": 21})
    signal.add(1_160, 3, "DL", "NAS", "AuthenticationRequest")
    signal.add(1_173, 3, "UL", "NAS", "AuthenticationResponse")
    signal.add(1_180, 3, "DL", "NAS", "SecurityModeCommand", sht=3, fields={"cipher": "5G-EA0", "integrity": "5G-IA2"})
    signal.add(1_186, 3, "UL", "NAS", "SecurityModeComplete", sht=4)
    signal.add(1_195, 3, "DL", "RRC", "SecurityModeCommand", fields={"cipher": "nea0", "integrity": "nia2"})
    signal.add(1_205, 3, "UL", "RRC", "SecurityModeComplete")
    signal.add(1_215, 3, "DL", "RRC", "UECapabilityEnquiry")
    signal.add(1_230, 3, "UL", "RRC", "UECapabilityInformation")
    signal.add(1_245, 3, "DL", "NAS", "RegistrationAccept")
    signal.add(1_255, 3, "UL", "NAS", "RegistrationComplete")
    return signal


def an_06a(mode: str, session: str) -> Signal:
    signal = Signal(session, "an-06a", 4_000)
    signal.normal_flow(1_000, 3, release_at=None)
    if mode != "control":
        signal.add(2_250, 3, "DL", "NAS", "AuthenticationRequest")
        signal.add(2_263, 3, "UL", "NAS", "AuthenticationResponse")
        signal.add(2_270, 3, "DL", "NAS", "SecurityModeCommand", sht=3, fields={"cipher": "5G-EA0", "integrity": "5G-IA2"})
        signal.add(2_276, 3, "UL", "NAS", "SecurityModeComplete", sht=4)
    return signal


def an_02(mode: str, session: str) -> Signal:
    count = 4 if mode == "control" else 5
    signal = Signal(session, "an-02", 8_000)
    for index in range(count):
        signal.normal_flow(
            1_000 + index * 1_000,
            index + 1,
            identity_request=True,
            registration_stmsi=STMSI_SHORT,
        )
    return signal


def short_connection(signal: Signal, start: int, du: int) -> None:
    signal.setup_head(start, du, stmsi=STMSI_SHORT, random=False)
    signal.add(start + 10, du, "UL", "RRC", "RRCSetupComplete", fields={"s_tmsi": STMSI_SHORT})
    signal.add(start + 20, du, "UL", "NAS", "ServiceRequest", fields={"s_tmsi": STMSI_SHORT})
    signal.add(start + 30, du, "DL", "NAS", "ServiceAccept")
    signal.add(start + 1_190, du, "DL", "RRC", "RRCRelease")
    signal.release(start + 1_200, du)


def an_04(mode: str, session: str) -> Signal:
    count = 2 if mode == "control" else 3
    signal = Signal(session, "an-04", 25_000)
    for index in range(count):
        short_connection(signal, 1_000 + index * 10_000, index + 1)
    return signal


def incomplete_setup(signal: Signal, start: int, du: int) -> None:
    signal.setup_head(start, du, stmsi=STMSI_SHORT, random=False)
    signal.release(start + 2_000, du)


def an_07(mode: str, session: str) -> Signal:
    count = 2 if mode == "control" else 3
    signal = Signal(session, "an-07", 25_000)
    for index in range(count):
        incomplete_setup(signal, 1_000 + index * 10_000, index + 1)
    return signal


def mobility_registration(signal: Signal, start: int, du: int, stmsi: str) -> None:
    signal.setup_head(start, du, stmsi=stmsi, random=False)
    signal.add(start + 10, du, "UL", "RRC", "RRCSetupComplete", fields={"s_tmsi": stmsi})
    signal.add(start + 20, du, "UL", "NAS", "RegistrationRequest", fields={"reg_type": "mobility", "id_type": "5G-GUTI", "s_tmsi": stmsi})
    signal.release(start + 6_000, du)


def an_08(mode: str, session: str) -> Signal:
    mobility_count = 4 if mode == "control" else 5
    signal = Signal(session, "an-08", 68_000)
    for index, stmsi in enumerate(STMSI_MOB):
        signal.normal_flow(1_000 + index * 2_000, index + 1, assigned_stmsi=stmsi)
    for index, stmsi in enumerate(STMSI_MOB[:mobility_count]):
        mobility_registration(signal, 21_000 + index * 10_000, 11 + index, stmsi)
    return signal


GENERATORS: dict[str, Callable[[str, str], Signal]] = {
    "AN-01": an_01,
    "AN-06a": an_06a,
    "AN-02": an_02,
    "AN-04": an_04,
    "AN-07": an_07,
    "AN-08": an_08,
}

ATTACK_OFFSET_MS = {
    "AN-01": 1_118,
    "AN-06a": 2_250,
    "AN-02": 5_095,
    "AN-04": 21_000,
    "AN-07": 21_000,
    "AN-08": 61_000,
}


def generate(scenario: str, mode: str, session: str, output: Path) -> dict[str, Any]:
    if scenario not in GENERATORS or mode not in {"control", "emulation"}:
        raise ValueError("지원하지 않는 scenario 또는 mode입니다")
    if output.parent.is_symlink() or not output.parent.is_dir():
        raise ValueError("출력 부모는 실제 디렉터리여야 합니다")
    signal = GENERATORS[scenario](mode, session)
    signal.write(output)
    generator = Path(__file__).resolve()
    return {
        "schema": "ran-reproducer.signal-source.v1",
        "generator": str(generator.relative_to(generator.parents[1])),
        "generator_sha256": hashlib.sha256(generator.read_bytes()).hexdigest(),
        "scenario": scenario,
        "mode": mode,
        "event_count": len(signal.events),
        "duration_ms": signal.duration_ms,
        "attack_started_at_ms": None if mode == "control" else BASE_MS + ATTACK_OFFSET_MS[scenario],
        "origin": "independent-reproducer-sequence",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=tuple(GENERATORS))
    parser.add_argument("mode", choices=("control", "emulation"))
    parser.add_argument("session")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        metadata = generate(args.scenario, args.mode, args.session, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
