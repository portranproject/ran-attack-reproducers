#!/usr/bin/env python3
"""Validate Blind DoS raw evidence and derive the independent phase verdict."""

import json
import os
from pathlib import Path
import re
import sys
import tempfile

from identity import format_5g_s_tmsi, split_5g_s_tmsi


RUN_SCHEMA = "blind.run.v1"
STOP_SCHEMA = "blind.run-stop.v1"
VERDICT_SCHEMA = "blind.phase-verdict.v1"
ATTACKER_SCHEMA = "blind.attacker-event.v1"
SERVICE_SCHEMA = "blind.victim-service.v1"
SNAPSHOT_SCHEMA = "blind.target-snapshot.v1"
NETWORK_SCHEMA = "blind.network-event.v1"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}")
SHA256 = re.compile(r"[0-9a-f]{64}")
EFFECTS = {"binding_changed", "pdu_session_deactivated", "ue_context_released"}
SERVICE_PHASES = {"before", "during", "recovery", "after"}
ROLES = {"target_owner_existing", "attacker_new", "infrastructure"}
NETWORK_EVENTS = EFFECTS | {"identity_reached", "observation", "process_crash", "forced_kill"}
VERDICT_BOOLS = (
    "infrastructure_valid", "victim_service_before", "victim_service_loss",
    "victim_service_after", "target_stable", "exact_join",
    "target_owner_state_effect", "same_victim_recovery",
)


def fail(message):
    raise ValueError(message)


def regular_file(path, label):
    if path.is_symlink() or not path.is_file():
        fail(f"{label} is not a regular file")


def load_object(path, label):
    regular_file(path, label)
    try:
        value = json.loads(path.read_text(errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot read valid {label}: {exc}")
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    return value


def load_jsonl(path, label, allow_empty=False):
    regular_file(path, label)
    rows = []
    try:
        lines = path.read_text(errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        fail(f"cannot read {label}: {exc}")
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"{label} line {number} is malformed: {exc}")
        if not isinstance(row, dict):
            fail(f"{label} line {number} must be a JSON object")
        rows.append(row)
    if not rows and not allow_empty:
        fail(f"{label} must contain at least one event")
    return rows


def require_schema_and_run_id(value, schema, run_id, label):
    if value.get("schema") != schema and value.get("schema_version") != schema:
        fail(f"{label} has the wrong schema")
    if value.get("run_id") != run_id:
        fail(f"{label} has the wrong run_id")


def nonnegative_integer(value, label):
    if type(value) is not int or value < 0:
        fail(f"{label} must be a non-negative integer")
    return value


def safe_name(value, label):
    if not isinstance(value, str) or not RUN_ID.fullmatch(value):
        fail(f"{label} must use 1..96 characters from [A-Za-z0-9._-]")
    return value


def validate_run(path):
    run = load_object(path, "run.json")
    if run.get("schema_version") != RUN_SCHEMA:
        fail("run.json has the wrong schema")
    run_id = safe_name(run.get("run_id"), "run.json run_id")
    mode = run.get("mode")
    if mode not in {"control", "attack"}:
        fail("run.json has an invalid mode")
    if type(run.get("attack_enabled")) is not bool \
            or run["attack_enabled"] != (mode == "attack"):
        fail("run.json attack_enabled does not match mode")
    thresholds = run.get("thresholds")
    if not isinstance(thresholds, dict):
        fail("run.json has no threshold contract")
    loss_consecutive = thresholds.get("loss_consecutive_pings")
    if type(loss_consecutive) is not int or loss_consecutive < 1:
        fail("run.json loss_consecutive_pings must be a positive integer")
    recovery_method = run.get("recovery_method")
    if recovery_method not in {None, "same_victim_process_after_one_shot_end"}:
        fail("run.json has an invalid recovery_method")
    return run, run_id, mode, loss_consecutive


def validate_snapshot(path, run_id, label):
    value = load_object(path, label)
    require_schema_and_run_id(value, SNAPSHOT_SCHEMA, run_id, label)
    if value.get("owner_role") != "target_owner_existing":
        fail(f"{label} owner_role must be target_owner_existing")
    safe_name(value.get("owner_id"), f"{label} owner_id")
    target = value.get("target_5g_s_tmsi")
    try:
        canonical = format_5g_s_tmsi(target)
    except ValueError as exc:
        fail(f"{label} has an invalid target_5g_s_tmsi: {exc}")
    if target != canonical:
        fail(f"{label} target_5g_s_tmsi is not canonical lowercase hex")
    part1, part2 = split_5g_s_tmsi(target)
    if value.get("part1") != part1 or value.get("part2") != part2:
        fail(f"{label} Part1/Part2 do not reconstruct target_5g_s_tmsi")
    nonnegative_integer(value.get("ran_ue_ngap_id"), f"{label} ran_ue_ngap_id")
    nonnegative_integer(value.get("amf_ue_ngap_id"), f"{label} amf_ue_ngap_id")
    nonnegative_integer(value.get("captured_realtime_ns"), f"{label} captured_realtime_ns")
    region = nonnegative_integer(value.get("amf_region_id"), f"{label} amf_region_id")
    if region > 0xFF:
        fail(f"{label} amf_region_id is out of range")
    if not isinstance(value.get("fiveg_guti"), str) or not value["fiveg_guti"]:
        fail(f"{label} must contain fiveg_guti")
    if not isinstance(value.get("source_sha256"), str) \
            or not SHA256.fullmatch(value["source_sha256"]):
        fail(f"{label} has an invalid source_sha256")
    return value


def validate_attacker_events(path, run_id, mode, target):
    rows = load_jsonl(path, "attacker_events.jsonl", allow_empty=mode == "control")
    if mode == "control" and rows:
        fail("control run must not contain attacker events")
    commits = []
    selected_gutis = []
    terminal_events = []
    previous_seq = 0
    previous_monotonic = -1
    for number, row in enumerate(rows, 1):
        label = f"attacker_events.jsonl line {number}"
        require_schema_and_run_id(row, ATTACKER_SCHEMA, run_id, label)
        seq = nonnegative_integer(row.get("seq"), f"{label} seq")
        if seq <= previous_seq:
            fail("attacker event sequence must be strictly increasing")
        previous_seq = seq
        nonnegative_integer(row.get("ue"), f"{label} ue")
        nonnegative_integer(row.get("realtime_ns"), f"{label} realtime_ns")
        monotonic = nonnegative_integer(row.get("monotonic_ns"), f"{label} monotonic_ns")
        if monotonic < previous_monotonic:
            fail("attacker monotonic timestamps move backwards")
        previous_monotonic = monotonic
        if not isinstance(row.get("event"), str) or not row["event"]:
            fail(f"{label} has no event name")
        if row["event"] == "target_msg3_committed":
            try:
                encoded = format_5g_s_tmsi(row.get("target_5g_s_tmsi"))
            except ValueError as exc:
                fail(f"{label} has an invalid target: {exc}")
            part1, part2 = split_5g_s_tmsi(encoded)
            if encoded != target or row.get("part1") != part1 or row.get("part2") != part2:
                fail(f"{label} target or identity split does not match the snapshot")
            if row.get("claim") != "payload_committed_not_air_confirmed":
                fail(f"{label} has an unexpected transmission claim")
            commits.append(row)
        elif row["event"] == "nas_guti_selected":
            selected_gutis.append(row)
        elif row["event"] == "authentication_request_withheld":
            if row.get("response_submitted") is not False:
                fail(f"{label} did not withhold the authentication response")
            terminal_events.append(row)
    if mode == "attack" and len(commits) != 1:
        fail("attack run must contain exactly one target_msg3_committed event")
    if mode == "attack":
        if len(selected_gutis) != 1 or len(terminal_events) != 1:
            fail("attack run must contain one NAS GUTI selection and one terminal event")
        target_value = int(target, 16)
        expected = {
            "amf_set_id": (target_value >> 38) & 0x3FF,
            "amf_pointer": (target_value >> 32) & 0x3F,
            "tmsi": target_value & 0xFFFFFFFF,
        }
        for field in ("amf_set_id", "amf_pointer", "tmsi"):
            if selected_gutis[0].get(field) != expected[field]:
                fail(f"nas_guti_selected {field} does not match the target")
    return commits[0] if commits else None, selected_gutis[0] if selected_gutis else None


def validate_service_events(path, run_id, owner_id, loss_consecutive):
    rows = load_jsonl(path, "victim_service.jsonl")
    selected = []
    for number, row in enumerate(rows, 1):
        label = f"victim_service.jsonl line {number}"
        require_schema_and_run_id(row, SERVICE_SCHEMA, run_id, label)
        safe_name(row.get("victim_id"), f"{label} victim_id")
        if row.get("phase") not in SERVICE_PHASES:
            fail(f"{label} has an invalid phase")
        for field in ("registration", "pdu_session", "ping_ok"):
            if type(row.get(field)) is not bool:
                fail(f"{label} {field} must be boolean")
        nonnegative_integer(row.get("realtime_ns"), f"{label} realtime_ns")
        pid = nonnegative_integer(row.get("victim_pid"), f"{label} victim_pid")
        if pid == 0:
            fail(f"{label} victim_pid must be positive")
        nonnegative_integer(row.get("registration_count"), f"{label} registration_count")
        nonnegative_integer(row.get("pdu_session_count"), f"{label} pdu_session_count")
        if row["victim_id"] == owner_id:
            selected.append(row)
    phases = {phase: [row for row in selected if row["phase"] == phase]
              for phase in SERVICE_PHASES}
    if any(not phases[phase] for phase in SERVICE_PHASES):
        fail("victim_service.jsonl lacks before/during/recovery/after rows for the target owner")
    for phase, phase_rows in phases.items():
        timestamps = [row["realtime_ns"] for row in phase_rows]
        if any(left >= right for left, right in zip(timestamps, timestamps[1:])):
            fail(f"victim service {phase} timestamps must be strictly increasing")
    if max(row["realtime_ns"] for row in phases["before"]) \
            >= min(row["realtime_ns"] for row in phases["during"]):
        fail("victim service before/during phases overlap or move backwards")
    if max(row["realtime_ns"] for row in phases["during"]) \
            >= min(row["realtime_ns"] for row in phases["recovery"]):
        fail("victim service during/recovery phases overlap or move backwards")
    if max(row["realtime_ns"] for row in phases["recovery"]) \
            >= min(row["realtime_ns"] for row in phases["after"]):
        fail("victim service recovery/after phases overlap or move backwards")
    healthy = lambda row: row["registration"] and row["pdu_session"] and row["ping_ok"]
    before = all(healthy(row) for row in phases["before"])
    streak = 0
    first_loss_ns = None
    for row in phases["during"]:
        streak = 0 if healthy(row) else streak + 1
        if streak == loss_consecutive:
            first_loss_ns = row["realtime_ns"]
            break
    after = all(healthy(row) for row in phases["after"])
    loss = first_loss_ns is not None
    recovery = loss and after and min(row["realtime_ns"] for row in phases["after"]) \
        > first_loss_ns
    victim_pids = {row["victim_pid"] for row in selected}
    baseline_registration = max(row["registration_count"] for row in phases["before"])
    baseline_pdu = max(row["pdu_session_count"] for row in phases["before"])
    recovery_registration = min(row["registration_count"] for row in phases["after"])
    recovery_pdu = min(row["pdu_session_count"] for row in phases["after"])
    return {
        "before": before,
        "loss": loss,
        "after": after,
        "recovery": recovery,
        "first_loss_ns": first_loss_ns,
        "same_pid": len(victim_pids) == 1,
        "counts_advanced": recovery_registration > baseline_registration
                           and recovery_pdu > baseline_pdu,
    }


def validate_network_events(path, run_id, before, commit):
    rows = load_jsonl(path, "ground_truth.jsonl")
    effects = []
    reaches = []
    crash_count = 0
    forced_kill_count = 0
    for number, row in enumerate(rows, 1):
        label = f"ground_truth.jsonl line {number}"
        require_schema_and_run_id(row, NETWORK_SCHEMA, run_id, label)
        role = row.get("role")
        event = row.get("event")
        if role not in ROLES or event not in NETWORK_EVENTS:
            fail(f"{label} has an invalid role or event")
        timestamp = nonnegative_integer(row.get("realtime_ns"), f"{label} realtime_ns")
        if type(row.get("exact_join")) is not bool:
            fail(f"{label} exact_join must be boolean")
        if role == "infrastructure":
            if event == "process_crash":
                crash_count += 1
            elif event == "forced_kill":
                forced_kill_count += 1
            else:
                fail(f"{label} infrastructure role may only report crash or forced kill")
            continue
        safe_name(row.get("owner_id"), f"{label} owner_id")
        try:
            target = format_5g_s_tmsi(row.get("target_5g_s_tmsi"))
        except ValueError as exc:
            fail(f"{label} has an invalid target: {exc}")
        if event == "identity_reached" and role == "attacker_new" \
                and row["exact_join"] and target == before["target_5g_s_tmsi"] \
                and (commit is None or timestamp >= commit["realtime_ns"]):
            reaches.append(row)
        elif event in EFFECTS:
            ran_id = nonnegative_integer(row.get("ran_ue_ngap_id"), f"{label} ran_ue_ngap_id")
            amf_id = nonnegative_integer(row.get("amf_ue_ngap_id"), f"{label} amf_ue_ngap_id")
            if role == "target_owner_existing" and row["exact_join"] \
                    and row["owner_id"] == before["owner_id"] \
                    and target == before["target_5g_s_tmsi"] \
                    and ran_id == before["ran_ue_ngap_id"] \
                    and amf_id == before["amf_ue_ngap_id"] \
                    and (commit is None or timestamp >= commit["realtime_ns"]):
                effects.append(row)
    joined = [effect for effect in effects
              if any(reach["realtime_ns"] <= effect["realtime_ns"] for reach in reaches)]
    return joined, crash_count, forced_kill_count


def evaluate_run(run_dir):
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        fail("run directory is not a real directory")
    run, run_id, mode, loss_consecutive = validate_run(run_dir / "run.json")
    before = validate_snapshot(run_dir / "target_snapshot_before.json", run_id,
                               "target_snapshot_before.json")
    after = validate_snapshot(run_dir / "target_snapshot_after.json", run_id,
                              "target_snapshot_after.json")
    target_stable = all(before[field] == after[field] for field in (
        "owner_role", "owner_id", "target_5g_s_tmsi", "part1", "part2",
        "amf_region_id",
    )) and before["captured_realtime_ns"] < after["captured_realtime_ns"]
    commit, selected_guti = validate_attacker_events(
        run_dir / "attacker_events.jsonl", run_id, mode, before["target_5g_s_tmsi"])
    if selected_guti is not None \
            and selected_guti.get("amf_region_id") != before["amf_region_id"]:
        fail("nas_guti_selected amf_region_id does not match the target snapshot")
    if commit is not None:
        target_stable = target_stable \
            and before["captured_realtime_ns"] <= commit["realtime_ns"] \
            <= after["captured_realtime_ns"]
    service = validate_service_events(
        run_dir / "victim_service.jsonl", run_id, before["owner_id"], loss_consecutive)
    effects, crash_count, forced_kill_count = validate_network_events(
        run_dir / "ground_truth.jsonl", run_id, before, commit)
    joined_effects = [row for row in effects if service["first_loss_ns"] is None
                      or row["realtime_ns"] <= service["first_loss_ns"]]
    target_effect = bool(joined_effects)
    return {
        "schema_version": VERDICT_SCHEMA,
        "run_id": run_id,
        "mode": mode,
        "infrastructure_valid": crash_count == 0 and forced_kill_count == 0,
        "victim_service_before": service["before"],
        "victim_service_loss": service["loss"],
        "victim_service_after": service["after"],
        "target_stable": target_stable,
        "exact_join": target_effect,
        "target_owner_state_effect": target_effect,
        "same_victim_recovery": service["recovery"] and service["same_pid"]
                                and service["counts_advanced"]
                                and run.get("recovery_method")
                                == "same_victim_process_after_one_shot_end",
        "crash_count": crash_count,
        "forced_kill_count": forced_kill_count,
    }


def normalize_verdict(value, run_id, mode, label="verdict.json"):
    if not isinstance(value, dict) or value.get("schema_version") != VERDICT_SCHEMA \
            or value.get("run_id") != run_id or value.get("mode") != mode:
        fail(f"{label} has inconsistent schema, run_id, or mode")
    if any(type(value.get(field)) is not bool for field in VERDICT_BOOLS):
        fail(f"{label} is missing a boolean verdict field")
    for field in ("crash_count", "forced_kill_count"):
        nonnegative_integer(value.get(field), f"{label} {field}")
    return {
        "schema_version": VERDICT_SCHEMA,
        "run_id": run_id,
        "mode": mode,
        **{field: value[field] for field in VERDICT_BOOLS},
        "crash_count": value["crash_count"],
        "forced_kill_count": value["forced_kill_count"],
    }


def atomic_create(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink():
        fail(f"{path.name} already exists")
    with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp = Path(handle.name)
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(temp, path)
    except FileExistsError:
        fail(f"{path.name} already exists")
    finally:
        temp.unlink(missing_ok=True)


def write_verdict(run_dir, output=None):
    run_dir = Path(run_dir)
    verdict = evaluate_run(run_dir)
    output = Path(output) if output is not None else run_dir / "verdict.json"
    atomic_create(output, verdict)
    return verdict


def _phase_passed(verdict):
    if not verdict["infrastructure_valid"] or verdict["crash_count"] \
            or verdict["forced_kill_count"]:
        return False
    if verdict["mode"] == "control":
        return verdict["victim_service_before"] and verdict["victim_service_after"] \
            and not verdict["victim_service_loss"] \
            and not verdict["target_owner_state_effect"]
    return all(verdict[field] for field in (
        "victim_service_before", "victim_service_loss", "victim_service_after",
        "target_stable", "exact_join", "target_owner_state_effect",
        "same_victim_recovery",
    ))


def validate_final(run_dir):
    """Validate the post-run metadata and replay the raw-evidence verdict."""
    run_dir = Path(run_dir)
    expected = evaluate_run(run_dir)
    run_id, mode = expected["run_id"], expected["mode"]
    stopped = load_object(run_dir / "run_stop.json", "run_stop.json")
    if stopped.get("schema_version") != STOP_SCHEMA \
            or stopped.get("run_id") != run_id or stopped.get("mode") != mode:
        fail("run_stop.json has inconsistent schema, run_id, or mode")
    classification = stopped.get("classification")
    if classification not in {"passed", "valid-failure", "infrastructure-invalid"}:
        fail("run_stop.json has an invalid classification")
    if type(stopped.get("passed")) is not bool or type(stopped.get("valid")) is not bool \
            or stopped["passed"] != (classification == "passed") \
            or stopped["valid"] != (classification != "infrastructure-invalid"):
        fail("run_stop.json passed/valid flags contradict classification")
    if not isinstance(stopped.get("reason"), str) or not stopped["reason"]:
        fail("run_stop.json has no reason")

    verdict_path = run_dir / "verdict.json"
    on_disk = None
    if verdict_path.exists() or verdict_path.is_symlink():
        on_disk = normalize_verdict(load_object(verdict_path, "verdict.json"), run_id, mode)
    embedded = stopped.get("verdict")
    if embedded is not None:
        embedded = normalize_verdict(embedded, run_id, mode, "run_stop.json verdict")
    if on_disk is not None and embedded is not None and on_disk != embedded:
        fail("verdict.json and run_stop.json verdict differ")
    if on_disk is not None and on_disk != expected:
        fail("verdict.json does not replay from raw evidence")
    if embedded is not None and embedded != expected:
        fail("run_stop.json verdict does not replay from raw evidence")

    if classification != "infrastructure-invalid":
        if on_disk is None or embedded is None:
            fail("valid run verdict does not replay from raw evidence")
        if not expected["infrastructure_valid"] or expected["crash_count"] \
                or expected["forced_kill_count"] or not expected["target_stable"]:
            fail("valid run classification contradicts an infrastructure-invalid verdict")
        expected_classification = "passed" if _phase_passed(expected) else "valid-failure"
        if classification != expected_classification:
            fail("run_stop.json classification contradicts the replayed verdict")
    elif _phase_passed(expected) and stopped.get("reason") == "matched_phase_contract_met":
        fail("infrastructure-invalid run uses the successful phase reason")
    return run_id, classification, expected


def main(argv):
    try:
        if len(argv) == 2 and argv[0] == "verify":
            run_id, classification, _ = validate_final(argv[1])
            print(f"blind-labels: verified run_id={run_id} classification={classification}")
        elif len(argv) in {1, 2}:
            verdict = write_verdict(argv[0], argv[1] if len(argv) == 2 else None)
            print(
                f"blind-labels: wrote run_id={verdict['run_id']} "
                f"target_effect={str(verdict['target_owner_state_effect']).lower()}"
            )
        else:
            print(
                "usage: export_labels.py RUN_DIR [OUTPUT]\n"
                "       export_labels.py verify RUN_DIR",
                file=sys.stderr,
            )
            return 2
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"blind-labels: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
