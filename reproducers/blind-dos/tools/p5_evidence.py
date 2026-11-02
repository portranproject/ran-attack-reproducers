#!/usr/bin/env python3
"""Build secret-free Blind DoS evidence from current-run p5 log slices."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from identity import format_5g_s_tmsi, split_5g_s_tmsi  # noqa: E402


SCHEMA = "blind.normalized-log.v1"
GUTI = re.compile(
    r"5G-GUTI:\s*AMF pointer\s+(?P<pointer>\d+)\s*,\s*"
    r"AMF Set ID\s+(?P<set>\d+)\s*,\s*5G-TMSI\s+(?P<tmsi>0x[0-9a-f]+|\d+)",
    re.IGNORECASE,
)
NGAP_IDS = re.compile(
    r"RAN_UE_NGAP_ID\[(?P<ran>\d+)\]\s+AMF_UE_NGAP_ID\[(?P<amf>\d+)\]"
)
FIVEG_S_TMSI = re.compile(
    r"5G-S_TMSI\[AMF_ID:0x(?P<amf_id>[0-9a-f]+),M_TMSI:0x(?P<tmsi>[0-9a-f]+)\]",
    re.IGNORECASE,
)
CU_CREATED = re.compile(
    r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+):\s+NGAP UE context created"
)
CU_BINDING = re.compile(
    r"ue=(?P<ue>\d+)\s+ran_ue=(?P<ran>\d+).*Setting AMF-UE-NGAP-ID=(?P<amf>\d+)"
)
RFC3339 = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<clock>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d{1,9}))?(?P<zone>Z|[+-]\d{2}:\d{2})"
)
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
OAI_IMSI = re.compile(r"\bimsi\s*=\s*([\"'])(?P<imsi>[0-9]{15})\1\s*;", re.I)
SUCI = re.compile(
    r"suci-[0-9]+-(?P<mcc>[0-9]{3})-(?P<mnc>[0-9]{2,3})-"
    r"[0-9]+-[0-9]+-[0-9]+-(?P<msin>[0-9]+)", re.I,
)
IMSI_LOG = re.compile(r"imsi-(?P<imsi>[0-9]{15})", re.I)


def fail(message):
    raise ValueError(message)


def regular_text(path, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        fail(f"{label} must be a regular non-symlink file")
    return path.read_text(encoding="utf-8", errors="strict")


def sha256(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def realtime_ns(line):
    match = RFC3339.search(line)
    if not match:
        return None
    zone = match.group("zone")
    if zone == "Z":
        tz = timezone.utc
    else:
        sign = 1 if zone[0] == "+" else -1
        hours, minutes = map(int, zone[1:].split(":"))
        tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
    base = datetime.fromisoformat(
        f"{match.group('date')}T{match.group('clock')}"
    ).replace(tzinfo=tz)
    fraction = int((match.group("fraction") or "").ljust(9, "0"))
    return int(base.timestamp()) * 1_000_000_000 + fraction


def target_from_amf(amf_id, m_tmsi):
    if not 0 <= amf_id <= 0xFFFFFF or not 0 <= m_tmsi <= 0xFFFFFFFF:
        fail("AMF ID or 5G-TMSI is out of range")
    return format_5g_s_tmsi(((amf_id & 0xFFFF) << 32) | m_tmsi)


def parse_victim_guti(text):
    matches = []
    for line in text.splitlines():
        match = GUTI.search(line)
        if not match:
            continue
        pointer = int(match.group("pointer"))
        amf_set = int(match.group("set"))
        m_tmsi = int(match.group("tmsi"), 0)
        if not 0 <= pointer <= 0x3F or not 0 <= amf_set <= 0x3FF \
                or not 0 <= m_tmsi <= 0xFFFFFFFF:
            fail("victim GUTI component is out of range")
        target = format_5g_s_tmsi(
            (amf_set << 38) | (pointer << 32) | m_tmsi
        )
        matches.append((target, amf_set, pointer, m_tmsi, line))
    if not matches:
        fail("victim log has no 5G-GUTI")
    if len({item[0] for item in matches}) != 1:
        fail("victim 5G-GUTI changed inside the phase")
    return matches[-1]


def marker(line):
    # shortcut: accept reviewed Open5GS v2.7.6 markers, add an adapter when G0 changes.
    if "InitialUEMessage" in line:
        return "initial_ue_message"
    if "Holding NG Context" in line:
        return "holding_ng_context"
    if "Clear NG Context" in line:
        return "clear_ng_context"
    if "UEContextReleaseCommand" in line:
        return "ue_context_release_command"
    if "UEContextReleaseComplete" in line:
        return "ue_context_release_complete"
    if "UEContextReleaseRequest" in line:
        return "ue_context_release_request"
    return None


def logged_imsi(line):
    match = IMSI_LOG.search(line)
    if match:
        return match.group("imsi")
    match = SUCI.search(line)
    if match:
        return match.group("mcc") + match.group("mnc") + match.group("msin")
    return None


def parse_amf(text, victim_imsi=None):
    """Return only allowlisted fields; subscriber strings never leave raw input."""
    rows = []
    pending_initial = None
    pending_effect = None
    for line in text.splitlines():
        event = marker(line)
        if event:
            if event == "initial_ue_message" and pending_initial is not None:
                rows.append(pending_initial)
                pending_initial = None
            pending = {
                "schema": SCHEMA,
                "source": "amf",
                "event": event,
                "source_sha256": sha256(line),
            }
            timestamp = realtime_ns(line)
            if timestamp is not None:
                pending["realtime_ns"] = timestamp
            if event == "initial_ue_message":
                pending_initial = pending
            else:
                if pending_effect is not None:
                    rows.append(pending_effect)
                pending_effect = pending
            continue

        identity_owner = logged_imsi(line)
        if identity_owner is not None and pending_initial is not None \
                and victim_imsi is not None:
            pending_initial["victim_profile_match"] = identity_owner == victim_imsi
            pending_initial["source_sha256"] = sha256(
                pending_initial["source_sha256"] + sha256(line)
            )
            continue

        identity = FIVEG_S_TMSI.search(line)
        if identity and pending_initial is not None:
            amf_id = int(identity.group("amf_id"), 16)
            m_tmsi = int(identity.group("tmsi"), 16)
            pending_initial["target_5g_s_tmsi"] = target_from_amf(amf_id, m_tmsi)
            pending_initial["source_sha256"] = sha256(
                pending_initial["source_sha256"] + sha256(line)
            )
            continue

        ids = NGAP_IDS.search(line)
        if ids:
            pending = pending_effect or pending_initial
            if pending is None:
                continue
            pending["ran_ue_ngap_id"] = int(ids.group("ran"))
            pending["amf_ue_ngap_id"] = int(ids.group("amf"))
            timestamp = realtime_ns(line)
            if "realtime_ns" not in pending and timestamp is not None:
                pending["realtime_ns"] = timestamp
            pending["source_sha256"] = sha256(
                pending["source_sha256"] + sha256(line)
            )
            if pending_effect is not None:
                rows.append(pending)
                pending_effect = None
    if pending_effect is not None:
        rows.append(pending_effect)
    if pending_initial is not None:
        rows.append(pending_initial)
    return rows


def parse_cu(text):
    rows = []
    for line in text.splitlines():
        created = CU_CREATED.search(line)
        binding = CU_BINDING.search(line)
        if not created and not binding:
            continue
        match = created or binding
        row = {
            "schema": SCHEMA,
            "source": "cu",
            "event": "ngap_context_created" if created else "ngap_binding",
            "ue_index": int(match.group("ue")),
            "ran_ue_ngap_id": int(match.group("ran")),
            "source_sha256": sha256(line),
        }
        if binding:
            row["amf_ue_ngap_id"] = int(match.group("amf"))
        timestamp = realtime_ns(line)
        if timestamp is not None:
            row["realtime_ns"] = timestamp
        rows.append(row)
    return rows


def meta_row(source, raw):
    return {
        "schema": SCHEMA,
        "source": source,
        "event": "slice_digest",
        "bytes": len(raw.encode()),
        "source_sha256": sha256(raw),
    }


def exclusive_json(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        fail(f"output already exists: {path}")
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True, separators=(",", ":"))
        output.write("\n")


def exclusive_jsonl(path, rows):
    path = Path(path)
    if path.exists() or path.is_symlink():
        fail(f"output already exists: {path}")
    with path.open("x", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def snapshot(args):
    run_id = args.run_id
    victim_id = args.victim_id
    if not RUN_ID.fullmatch(run_id) or not RUN_ID.fullmatch(victim_id):
        fail("run-id and victim-id must be safe aliases")
    victim_text = regular_text(args.victim_log, "victim log")
    victim_config = regular_text(args.victim_config, "victim config")
    imsi_matches = list(OAI_IMSI.finditer(victim_config))
    if len(imsi_matches) != 1:
        fail("victim config must contain exactly one IMSI")
    victim_imsi = imsi_matches[0].group("imsi")
    amf_text = regular_text(args.amf_raw, "AMF raw slice")
    target, amf_set, pointer, m_tmsi, source_line = parse_victim_guti(victim_text)

    if args.phase == "before":
        candidates = [row for row in parse_amf(amf_text, victim_imsi)
                      if row["event"] == "initial_ue_message"
                      and row.get("victim_profile_match") is True
                      and "ran_ue_ngap_id" in row and "amf_ue_ngap_id" in row]
        if len(candidates) != 1:
            fail("before snapshot needs exactly one current-run InitialUEMessage mapping")
        ids = candidates[0]
        material = source_line + "\n" + json.dumps(ids, sort_keys=True)
    else:
        before_path = Path(args.before)
        before = json.loads(regular_text(before_path, "before snapshot"))
        if before.get("schema") != "blind.target-snapshot.v1" \
                or before.get("run_id") != run_id \
                or before.get("owner_id") != victim_id \
                or before.get("target_5g_s_tmsi") != target:
            fail("after snapshot does not match the before target owner")
        ids = before
        material = source_line + "\n" + json.dumps({
            "target_5g_s_tmsi": target,
            "ran_ue_ngap_id": before["ran_ue_ngap_id"],
            "amf_ue_ngap_id": before["amf_ue_ngap_id"],
            "amf_slice_sha256": sha256(amf_text),
        }, sort_keys=True)

    part1, part2 = split_5g_s_tmsi(target)
    exclusive_json(args.output, {
        "schema": "blind.target-snapshot.v1",
        "run_id": run_id,
        "owner_role": "target_owner_existing",
        "owner_id": victim_id,
        "fiveg_guti": (
            f"amf-set={amf_set};amf-pointer={pointer};5g-tmsi=0x{m_tmsi:08x}"
        ),
        "target_5g_s_tmsi": target,
        "part1": part1,
        "part2": part2,
        "ran_ue_ngap_id": ids["ran_ue_ngap_id"],
        "amf_ue_ngap_id": ids["amf_ue_ngap_id"],
        "captured_realtime_ns": time.time_ns(),
        "source_sha256": sha256(material),
    })


def normalize(args):
    for source, input_path, output_path in (
        ("amf", args.amf_raw, args.amf_output),
        ("cu", args.cu_raw, args.cu_output),
        ("du", args.du_raw, args.du_output),
    ):
        raw = regular_text(input_path, f"{source.upper()} raw slice")
        rows = [meta_row(source, raw)]
        if source == "amf":
            rows.extend(parse_amf(raw))
            if not any(row["event"] == "initial_ue_message" for row in rows):
                fail("AMF slice has no InitialUEMessage")
        elif source == "cu":
            rows.extend(parse_cu(raw))
        exclusive_jsonl(output_path, rows)


def load_json(path, label):
    value = json.loads(regular_text(path, label))
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value


def load_jsonl(path, label, allow_empty=False):
    rows = []
    for number, line in enumerate(regular_text(path, label).splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            fail(f"{label} line {number} must be an object")
        rows.append(value)
    if not rows and not allow_empty:
        fail(f"{label} is empty")
    return rows


def network_events(args):
    if not RUN_ID.fullmatch(args.run_id):
        fail("run-id must be a safe alias")
    before = load_json(args.before, "before snapshot")
    if before.get("schema") != "blind.target-snapshot.v1" \
            or before.get("run_id") != args.run_id:
        fail("before snapshot does not match run-id")
    target = format_5g_s_tmsi(before.get("target_5g_s_tmsi"))
    if before.get("target_5g_s_tmsi") != target \
            or not RUN_ID.fullmatch(str(before.get("owner_id", ""))):
        fail("before snapshot has an invalid target owner")
    for field, maximum in (("ran_ue_ngap_id", (1 << 32) - 1),
                           ("amf_ue_ngap_id", (1 << 40) - 1)):
        value = before.get(field)
        if type(value) is not int or not 0 <= value <= maximum:
            fail(f"before snapshot has an invalid {field}")
    amf_rows = load_jsonl(args.amf_log, "normalized AMF log")
    if any(row.get("schema") != SCHEMA or row.get("source") != "amf"
           for row in amf_rows):
        fail("normalized AMF log has an invalid row")
    commits = load_jsonl(
        args.attacker_events, "attacker events", allow_empty=args.mode == "control"
    )
    commits = [row for row in commits if row.get("event") == "target_msg3_committed"]
    if args.mode == "attack" and len(commits) != 1:
        fail("attack mode needs exactly one target_msg3_committed event")
    if args.mode == "control" and commits:
        fail("control mode cannot contain a target commit")
    for commit in commits:
        if commit.get("schema") != "blind.attacker-event.v1" \
                or commit.get("run_id") != args.run_id \
                or commit.get("target_5g_s_tmsi") != target \
                or type(commit.get("realtime_ns")) is not int:
            fail("target commit does not match the current run and snapshot")

    old_ids = (before["ran_ue_ngap_id"], before["amf_ue_ngap_id"])
    commit_ns = commits[0]["realtime_ns"] if commits else None
    output = []
    seen = set()
    for row in amf_rows:
        timestamp = row.get("realtime_ns")
        if commit_ns is None or type(timestamp) is not int or timestamp < commit_ns:
            continue
        event = row.get("event")
        ids = (row.get("ran_ue_ngap_id"), row.get("amf_ue_ngap_id"))
        if event == "initial_ue_message" and row.get("target_5g_s_tmsi") == target \
                and None not in ids:
            key = ("identity_reached", ids, timestamp)
            if key not in seen:
                output.append({
                    "schema": "blind.network-event.v1",
                    "run_id": args.run_id,
                    "role": "attacker_new",
                    "owner_id": "attacker-new",
                    "target_5g_s_tmsi": target,
                    "event": "identity_reached",
                    "exact_join": True,
                    "realtime_ns": timestamp,
                })
                seen.add(key)
        effect = {
            "holding_ng_context": "binding_changed",
            "clear_ng_context": "ue_context_released",
            "ue_context_release_command": "ue_context_released",
            "ue_context_release_complete": "ue_context_released",
        }.get(event)
        if effect and ids == old_ids:
            key = (effect, ids, timestamp)
            if key not in seen:
                output.append({
                    "schema": "blind.network-event.v1",
                    "run_id": args.run_id,
                    "role": "target_owner_existing",
                    "owner_id": before["owner_id"],
                    "target_5g_s_tmsi": target,
                    "event": effect,
                    "exact_join": True,
                    "ran_ue_ngap_id": old_ids[0],
                    "amf_ue_ngap_id": old_ids[1],
                    "realtime_ns": timestamp,
                })
                seen.add(key)

    if not output:
        output.append({
            "schema": "blind.network-event.v1",
            "run_id": args.run_id,
            "role": "target_owner_existing",
            "owner_id": before["owner_id"],
            "target_5g_s_tmsi": target,
            "event": "observation",
            "exact_join": False,
            "realtime_ns": time.time_ns(),
        })
    exclusive_jsonl(args.output, output)


def env(name):
    return os.environ.get(name)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)

    snap = commands.add_parser("snapshot")
    snap.add_argument("--victim-log", default=env("BLIND_VICTIM_LOG_PATH"), required=not env("BLIND_VICTIM_LOG_PATH"))
    snap.add_argument("--victim-config", default=env("VICTIM_UE_CFG"), required=not env("VICTIM_UE_CFG"))
    snap.add_argument("--amf-raw", default=env("BLIND_AMF_RAW_LOG"), required=not env("BLIND_AMF_RAW_LOG"))
    snap.add_argument("--output", default=env("BLIND_SNAPSHOT_PATH"), required=not env("BLIND_SNAPSHOT_PATH"))
    snap.add_argument("--phase", choices=("before", "after"), default=env("BLIND_SNAPSHOT_PHASE"), required=not env("BLIND_SNAPSHOT_PHASE"))
    snap.add_argument("--before", default=None)
    snap.add_argument("--run-id", default=env("BLIND_RUN_ID"), required=not env("BLIND_RUN_ID"))
    snap.add_argument("--victim-id", default=env("VICTIM_ID"), required=not env("VICTIM_ID"))
    snap.set_defaults(function=snapshot)

    norm = commands.add_parser("normalize")
    for source in ("amf", "cu", "du"):
        norm.add_argument(f"--{source}-raw", required=True)
        norm.add_argument(f"--{source}-output", required=True)
    norm.set_defaults(function=normalize)

    events = commands.add_parser("network-events")
    events.add_argument("--amf-log", default=env("BLIND_AMF_LOG_PATH"), required=not env("BLIND_AMF_LOG_PATH"))
    events.add_argument("--before", required=True)
    events.add_argument("--attacker-events", default=env("BLIND_ATTACKER_EVENTS_PATH"), required=not env("BLIND_ATTACKER_EVENTS_PATH"))
    events.add_argument("--output", default=env("BLIND_NETWORK_EVENTS_PATH"), required=not env("BLIND_NETWORK_EVENTS_PATH"))
    events.add_argument("--run-id", default=env("BLIND_RUN_ID"), required=not env("BLIND_RUN_ID"))
    events.add_argument("--mode", choices=("control", "attack"), default=env("BLIND_MODE"), required=not env("BLIND_MODE"))
    events.set_defaults(function=network_events)
    return result


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.command == "snapshot" and args.phase == "after" and args.before is None:
            args.before = str(Path(args.output).with_name("target_snapshot_before.json"))
        args.function(args)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"blind-p5-evidence: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
