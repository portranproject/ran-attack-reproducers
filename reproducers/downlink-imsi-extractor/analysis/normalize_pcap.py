#!/usr/bin/env python3
"""tshark의 제한된 NAS 필드에서 탐지 입력과 가입자 oracle을 분리한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

MESSAGE = {
    "0x41": ("uplink", "RegistrationRequest"),
    "0x56": ("downlink", "AuthenticationRequest"),
    "0x57": ("uplink", "AuthenticationResponse"),
    "0x5b": ("downlink", "IdentityRequest"),
    "0x5c": ("uplink", "IdentityResponse"),
}


def normalize(tsv: Path, expected_fingerprint: str) -> tuple[list[dict], dict]:
    if tsv.is_symlink() or not tsv.is_file() or re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint) is None:
        raise ValueError("안전한 tshark 원문과 가입자 fingerprint가 필요합니다")
    with tsv.open(newline="", encoding="utf-8") as source:
        rows = [row for row in csv.DictReader(source, delimiter="\t") if row.get("message_type") in MESSAGE]
    if not rows:
        raise ValueError("지원하는 NAS 메시지가 없습니다")
    ids = {(row["ran_id"], row["amf_id"]) for row in rows if row.get("amf_id")}
    if len(ids) != 1:
        raise ValueError("단일 RAN/AMF UE context를 고를 수 없습니다")
    ran_id, amf_id = next(iter(ids))
    selected = [row for row in rows if row.get("ran_id") == ran_id and row.get("amf_id", amf_id) in {"", amf_id}]
    observations = []
    identity = None
    scheme = None
    for row in selected:
        direction, message = MESSAGE[row["message_type"]]
        row_scheme = int(row["scheme_id"]) if row.get("scheme_id") else None
        if row_scheme is not None:
            scheme = row_scheme
        if message == "IdentityResponse" and row_scheme == 0:
            parts = (row.get("mcc", ""), row.get("mnc", ""), row.get("msin", ""))
            if not all(re.fullmatch(r"[0-9]+", part) for part in parts):
                raise ValueError("null-scheme SUCI 식별자 필드가 불완전합니다")
            identity = hashlib.sha256("".join(parts).encode()).hexdigest()
        observations.append({
            "schema": "downlink-imsi.observation.v1", "order": len(observations), "source": "ngap",
            "direction": direction, "message": message, "ran_ue_ngap_id": int(ran_id),
            "amf_ue_ngap_id": int(amf_id), "realtime_ns": round(float(row["time_epoch"]) * 1_000_000_000),
            "nas_security": "plain",
        })
    if scheme is None:
        raise ValueError("SUCI protection scheme을 관측하지 못했습니다")
    oracle = {
        "schema": "downlink-imsi.oracle.v1", "protection_scheme": scheme,
        "expected_subscriber_fingerprint": expected_fingerprint,
        "observed_subscriber_fingerprint": identity,
    }
    return observations, oracle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tshark_tsv", type=Path)
    parser.add_argument("expected_fingerprint")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        observations, oracle = normalize(args.tshark_tsv.resolve(), args.expected_fingerprint)
        output = args.output_dir.resolve()
        for name in ("observations.jsonl", "oracle.json"):
            if (output / name).exists() or (output / name).is_symlink():
                raise ValueError(f"기존 {name}은 덮어쓰지 않습니다")
        (output / "observations.jsonl").write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in observations), encoding="utf-8")
        (output / "oracle.json").write_text(json.dumps(oracle, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, csv.Error) as error:
        print(f"pcap 정규화 실패: {error}", file=sys.stderr)
        return 2
    print(f"pcap 정규화: {len(observations)}개 NAS 메시지, scheme={oracle['protection_scheme']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
