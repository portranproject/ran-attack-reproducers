#!/usr/bin/env python3
"""Export conservative per-attempt ground truth from one rss-run.

usage: export_labels.py RUN_JSON ATTEMPTS_JSONL [RUN_SCOPED_GNB_LOG]

The input event log is immutable evidence.  This exporter joins events by
(run_id, ue, seq) and writes one schema-v1 JSON object per attempt to stdout.
It never turns a missing Msg4-ACK event into a successful canonical A attempt.
The optional gNB log must contain only the current run's byte range.
"""

import hashlib
import json
from pathlib import Path
import re
import sys


RECOGNIZED = {
    "attempt_start",
    "msg3_tx",
    "msg3_retx",
    "msg4_rx",
    "msg4_ack_scheduled",
    "msg4_ack_withheld",
    "rrc_reject",
    "attempt_end",
    "retrigger",
    "msg5_submitted",
}
FAPI_UCI = re.compile(
    r"Sector#(?P<sector>\d+):\s*"
    r"UCI\.indication\s+slot=(?P<frame>\d+)\.(?P<slot>\d+)\s+"
    r"PUCCH format 0/1\b.*?\brnti=(?P<rnti>0x[0-9a-fA-F]+|\d+)\b.*?"
    r"\bHARQ:\s*harq_ack=(?P<outcomes>[A-Za-z]+(?:,[A-Za-z]+)*)"
)
FAPI_SECTOR = re.compile(r"Sector#(?P<sector>\d+):")
CU_RRC_SETUP = re.compile(
    r"\bue=(?P<ue>\d+)\s+c-rnti=(?P<rnti>0x[0-9a-fA-F]+|\d+):\s*"
    r"Rx SRB0 CCCH UL rrcSetupRequest\b"
)


def fail(message):
    raise ValueError(message)


def load_object(path, label):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be one JSON object")
    return value


def first(records, event):
    matches = [record for record in records if record["event"] == event]
    return min(matches, key=lambda record: record["t_ns"]) if matches else None


def first_value(records, field):
    for record in sorted(records, key=lambda item: item["t_ns"]):
        if field in record:
            return record[field]
    return None


def timestamp(record):
    return record["t_ns"] if record else None


def parse_rnti(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value, 0)
        except ValueError:
            return None
    else:
        return None
    return result if 0 < result <= 0xffff else None


def parse_msg3_evidence(record):
    if record is None:
        return None
    rnti = parse_rnti(record.get("tc_rnti"))
    frame, slot = record.get("frame"), record.get("slot")
    if (rnti is None or isinstance(frame, bool) or not isinstance(frame, int)
            or isinstance(slot, bool) or not isinstance(slot, int)
            or not 0 <= frame <= 1023 or not 0 <= slot <= 159):
        fail("msg3_tx event has invalid TC-RNTI, frame or slot")
    return {
        "source": record.get("source", "ue_mac"),
        "tc_rnti": f"0x{rnti:04x}",
        "frame": frame,
        "slot": slot,
    }


def load_gnb_indexes(path, expected_sector):
    try:
        raw = Path(path).read_bytes()
        content = raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        fail(f"cannot read run-scoped gNB log: {exc}")
    digest = hashlib.sha256(raw).hexdigest()
    du_index = {}
    cu_index = {}
    for line_number, line in enumerate(content.splitlines(), 1):
        candidate = all(token in line for token in (
            "UCI.indication", "PUCCH format 0/1", "HARQ:",
        ))
        if candidate and (type(expected_sector) is not int
                          or not 0 <= expected_sector <= 65535):
            fail("run JSON needs orchestration.du_sector_id for a DU log join")
        sector_match = FAPI_SECTOR.search(line) if candidate else None
        if sector_match is not None and int(sector_match.group("sector")) != expected_sector:
            continue
        match = FAPI_UCI.search(line)
        if candidate and match is None:
            fail(f"run-scoped DU log line {line_number} has malformed FAPI HARQ evidence")
        if match is not None:
            sector = int(match.group("sector"))
            frame = int(match.group("frame"))
            slot = int(match.group("slot"))
            rnti = parse_rnti(match.group("rnti"))
            outcomes = tuple(item.casefold() for item in match.group("outcomes").split(","))
            if rnti is None or not 0 <= frame <= 1023 or not 0 <= slot <= 159:
                fail(f"run-scoped DU log line {line_number} has out-of-range FAPI identity")
            if not outcomes or any(item not in {"ack", "dtx", "nack"} for item in outcomes):
                fail(f"run-scoped DU log line {line_number} has unknown HARQ outcome")
            du_index.setdefault((rnti, frame, slot), []).append({
                "line": line_number,
                "sector_id": sector,
                "outcomes": outcomes,
            })

        cu_candidate = "Rx SRB0 CCCH UL rrcSetupRequest" in line
        cu_match = CU_RRC_SETUP.search(line)
        if cu_candidate and cu_match is None:
            fail(f"run-scoped CU log line {line_number} has malformed RRC Setup evidence")
        if cu_match is not None:
            rnti = parse_rnti(cu_match.group("rnti"))
            ue = int(cu_match.group("ue"))
            if rnti is None:
                fail(f"run-scoped CU log line {line_number} has out-of-range RRC identity")
            cu_index.setdefault(rnti, []).append({"line": line_number, "ue": ue})
    return du_index, cu_index, digest


def scheduled_du_keys(records):
    fallback_rnti = first_value(records, "tc_rnti")
    scheduled = sorted(
        (record for record in records if record["event"] == "msg4_ack_scheduled"),
        key=lambda record: record["t_ns"],
    )
    for record in scheduled:
        rnti = parse_rnti(record.get("tc_rnti", record.get("rnti", fallback_rnti)))
        frame, slot = record.get("frame"), record.get("slot")
        if (rnti is None or isinstance(frame, bool) or not isinstance(frame, int)
                or isinstance(slot, bool) or not isinstance(slot, int)
                or not 0 <= frame <= 1023 or not 0 <= slot <= 159):
            continue
        yield rnti, frame, slot


def find_du_ack(records, du_index, du_log_sha256, ue_tuple_counts):
    for key in scheduled_du_keys(records):
        if ue_tuple_counts.get(key) != 1:
            continue
        matches = du_index.get(key, [])
        if len(matches) != 1 or matches[0]["outcomes"] != ("ack",):
            continue
        rnti, frame, slot = key
        return {
            "source": "ocudu_fapi_uci",
            "log_sha256": du_log_sha256,
            "line": matches[0]["line"],
            "sector_id": matches[0]["sector_id"],
            "rnti": f"0x{rnti:04x}",
            "frame": frame,
            "slot": slot,
        }
    return None


def find_cu_msg3(msg3_evidence, cu_index, log_sha256, ue_rnti_counts):
    if msg3_evidence is None or cu_index is None:
        return None
    rnti = parse_rnti(msg3_evidence["tc_rnti"])
    matches = cu_index.get(rnti, [])
    if ue_rnti_counts.get(rnti) != 1 or len(matches) != 1:
        return None
    return {
        "source": "ocudu_cu_rrc",
        "log_sha256": log_sha256,
        "line": matches[0]["line"],
        "ue": matches[0]["ue"],
        "rnti": f"0x{rnti:04x}",
    }


def classify(records, scenario, du_index=None, cu_index=None,
             gnb_log_sha256=None, ue_tuple_counts=None, ue_rnti_counts=None):
    start = first(records, "attempt_start")
    msg3 = first(records, "msg3_tx")
    msg3_evidence = parse_msg3_evidence(msg3)
    msg4 = first(records, "msg4_rx")
    scheduled = first(records, "msg4_ack_scheduled")
    withheld = first(records, "msg4_ack_withheld")
    rejected = first(records, "rrc_reject")
    msg5 = first(records, "msg5_submitted")
    ended = first(records, "attempt_end")
    retrigger = first(records, "retrigger")

    msg5_action = msg4.get("msg5_action") if msg4 else None
    if msg4 and msg5_action is None and msg4.get("actual_reach") == "msg5_skip":
        msg5_action = "skipped"  # legacy raw event; ACK still needs evidence

    if scheduled and withheld:
        ack_state = "conflict"
    elif scheduled:
        ack_state = "scheduled"
    elif withheld:
        ack_state = "withheld"
    else:
        ack_state = "unknown"

    canonical_msg3_ue = False
    canonical_msg3 = False
    # Order is part of label-v1: terminal RRC outcomes beat lower-layer hints.
    if rejected:
        reach, canonical_ue, canonical, evidence = "rrc_reject", False, False, "ue_rrc"
    elif msg5:
        reach, canonical_ue, canonical, evidence = "msg5_submitted", False, False, "ue_pdcp"
    elif ack_state == "conflict":
        reach, canonical_ue, canonical, evidence = "inconclusive", None, None, "conflicting_ue_events"
    elif msg4 and withheld:
        reach, canonical_ue, canonical, evidence = "msg4_no_ack", False, False, "ue_scheduler"
    elif msg4 and scheduled and msg5_action == "skipped":
        reach, canonical_ue, canonical, evidence = "msg5_skip", True, None, "du_ack_missing"
    elif msg4 and msg5_action == "skipped":
        reach, canonical_ue, canonical, evidence = "msg4_ack_unknown", None, None, "missing_ue_ack_event"
    elif scenario == "A_early" and msg3_evidence is not None:
        reach, canonical_ue, canonical, evidence = "msg3_sent", False, False, "not_canonical_a"
        canonical_msg3_ue = True
        canonical_msg3 = None
    elif ended and ended.get("actual_reach") == "no_msg4":
        reach, canonical_ue, canonical, evidence = "no_msg4", False, False, "ue_attempt_end"
    else:
        reach, canonical_ue, canonical, evidence = "unknown", None, None, None

    result = {
        "actual_reach": reach,
        "canonical_a_ue": canonical_ue,
        "canonical_a": canonical,
        "canonical_a_evidence": evidence,
        "canonical_msg3_ue": canonical_msg3_ue,
        "canonical_msg3_only": canonical_msg3,
        "canonical_msg3_evidence": "gnb_receive_missing" if canonical_msg3_ue else None,
        "cu_msg3_evidence": None,
        "msg3_tx_evidence": msg3_evidence,
        "msg4_ack_state": ack_state,
        "du_ack_state": "unknown",
        "msg5_action": msg5_action,
        "ue_identity": start.get("ue_identity") if start else None,
        "identity_type": start.get("identity_type") if start else None,
        "tc_rnti": first_value(records, "tc_rnti"),
        "intended_reach": first_value(records, "intended_reach"),
        "timestamps": {
            "attempt_start_ns": timestamp(start),
            "msg3_tx_ns": timestamp(msg3),
            "msg4_rx_ns": timestamp(msg4),
            "msg4_ack_scheduled_ns": timestamp(scheduled),
            "msg4_ack_withheld_ns": timestamp(withheld),
            "rrc_reject_ns": timestamp(rejected),
            "msg5_submitted_ns": timestamp(msg5),
            "attempt_end_ns": timestamp(ended),
            "retrigger_ns": timestamp(retrigger),
        },
    }
    if du_index is not None:
        result["du_ack_evidence"] = None
        if canonical_ue is True:
            du_evidence = find_du_ack(
                records, du_index, gnb_log_sha256, ue_tuple_counts,
            )
            if du_evidence is not None:
                result["du_ack_state"] = "ack"
                result["canonical_a"] = True
                result["canonical_a_evidence"] = "ue_scheduler+ocudu_fapi"
                result["du_ack_evidence"] = du_evidence
    if canonical_msg3_ue:
        cu_evidence = find_cu_msg3(
            msg3_evidence, cu_index, gnb_log_sha256, ue_rnti_counts,
        )
        if cu_evidence is not None:
            result["canonical_msg3_only"] = True
            result["canonical_msg3_evidence"] = "ue_mac+ocudu_cu_rrc"
            result["cu_msg3_evidence"] = cu_evidence
    return result


def export(run_path, events_path, gnb_log_path=None):
    run = load_object(run_path, "run JSON")
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        fail("run JSON has no non-empty string run_id")

    du_index, cu_index, gnb_log_sha256 = (None, None, None)
    if gnb_log_path is not None:
        orchestration = run.get("orchestration")
        expected_sector = (
            orchestration.get("du_sector_id") if isinstance(orchestration, dict)
            else None
        )
        du_index, cu_index, gnb_log_sha256 = load_gnb_indexes(
            gnb_log_path, expected_sector,
        )

    groups = {}
    try:
        handle = Path(events_path).open(errors="strict")
    except OSError as exc:
        fail(f"cannot read attempts JSONL: {exc}")
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(f"attempts JSONL line {line_number} is malformed: {exc}")
            if not isinstance(record, dict):
                fail(f"attempts JSONL line {line_number} is not an object")
            if record.get("run_id") != run_id:
                fail(f"attempts JSONL line {line_number} run_id does not match {run_id}")
            if record.get("event") not in RECOGNIZED:
                continue
            ue, seq, t_ns = record.get("ue"), record.get("seq"), record.get("t_ns")
            if type(ue) is not int or ue < 0 or type(seq) is not int or seq < 0:
                fail(f"attempts JSONL line {line_number} has invalid ue or seq")
            if type(t_ns) is not int or t_ns < 0:
                fail(f"attempts JSONL line {line_number} has invalid t_ns")
            groups.setdefault((run_id, ue, seq), []).append(record)

    ue_tuple_counts = {}
    ue_rnti_counts = {}
    if gnb_log_path is not None:
        for records in groups.values():
            for key in scheduled_du_keys(records):
                ue_tuple_counts[key] = ue_tuple_counts.get(key, 0) + 1
            msg3 = first(records, "msg3_tx")
            if msg3 is not None:
                rnti = parse_rnti(msg3.get("tc_rnti"))
                if rnti is not None:
                    ue_rnti_counts[rnti] = ue_rnti_counts.get(rnti, 0) + 1

    rows = []
    for (group_run_id, ue, seq), records in groups.items():
        result = classify(
            records, run.get("scenario"), du_index, cu_index, gnb_log_sha256,
            ue_tuple_counts, ue_rnti_counts,
        )
        result.update({
            "schema_version": 1,
            "type": "attempt",
            "source": "ue_ground_truth",
            "run_id": group_run_id,
            "attempt_id": f"{group_run_id}:{ue}:{seq}",
            "ue": ue,
            "seq": seq,
            "scenario": run.get("scenario"),
            "event_count": len(records),
        })
        rows.append(result)

    rows.sort(key=lambda row: (
        row["timestamps"]["attempt_start_ns"] is None,
        row["timestamps"]["attempt_start_ns"] or min(
            value for value in row["timestamps"].values() if value is not None
        ),
        row["ue"],
        row["seq"],
    ))
    return rows


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        rows = export(*argv)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"export_labels: {exc}", file=sys.stderr)
        return 1
    for row in rows:
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
