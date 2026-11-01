#!/usr/bin/env python3
"""Validate an OTA G0 inventory without probing hardware or enabling RF."""

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys


PLACEHOLDERS = {"", "tbd", "todo", "unknown", "unmeasured", "unset", "null", "none"}
BANNED_KEYS = {
    "imsi", "supi", "k", "ki", "op", "opc", "raw_serial", "serial",
    "serial_number", "subscriber_key", "secret", "password", "pin", "puk",
}
ROLES = {"du", "attack_ue", "witness_ue"}


def normalized_key(value):
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def scan_banned_keys(value, path, errors):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if normalized_key(str(key)) in BANNED_KEYS:
                errors.append(f"{child_path}: secret or raw identifier keys are forbidden")
            scan_banned_keys(child, child_path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_banned_keys(child, f"{path}[{index}]", errors)


def object_value(value, path, required, errors):
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return {}
    unknown = sorted(set(value) - set(required))
    missing = sorted(set(required) - set(value))
    for key in unknown:
        errors.append(f"{path}.{key}: unknown field")
    for key in missing:
        errors.append(f"{path}.{key}: missing")
    return value


def list_value(value, path, errors, minimum=1):
    if not isinstance(value, list):
        errors.append(f"{path}: must be an array")
        return []
    if len(value) < minimum:
        errors.append(f"{path}: needs at least {minimum} item(s)")
    return value


def text_value(obj, key, path, errors):
    value = obj.get(key)
    field = f"{path}.{key}"
    if not isinstance(value, str) or value.strip().casefold() in PLACEHOLDERS:
        errors.append(f"{field}: needs a concrete non-placeholder string")
        return None
    return value.strip()


def number_value(obj, key, path, errors, minimum=None):
    value = obj.get(key)
    field = f"{path}.{key}"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        errors.append(f"{field}: must be a finite number")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{field}: must be >= {minimum}")
        return None
    return value


def true_value(obj, key, path, errors):
    if obj.get(key) is not True:
        errors.append(f"{path}.{key}: must be true")


def validate_timestamp(value, path, errors):
    if not isinstance(value, str):
        errors.append(f"{path}: needs an ISO-8601 timestamp with timezone")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        errors.append(f"{path}: needs an ISO-8601 timestamp with timezone")


def validate(data):
    errors = []
    scan_banned_keys(data, "$", errors)
    top_keys = {
        "schema_version", "lab_id", "equipment_owned_by_team",
        "subscriber_profiles_owned_by_team", "physical_crosscheck_complete",
        "endpoints", "rf_paths", "leakage", "subscribers", "witness", "approvals",
    }
    root = object_value(data, "$", top_keys, errors)
    if root.get("schema_version") != 1:
        errors.append("$.schema_version: must be 1")
    text_value(root, "lab_id", "$", errors)
    for key in (
        "equipment_owned_by_team", "subscriber_profiles_owned_by_team",
        "physical_crosscheck_complete",
    ):
        true_value(root, key, "$", errors)

    endpoint_keys = {
        "alias", "role", "host_alias", "model", "serial_hash", "rf_port", "channel",
        "antenna_alias", "backend", "driver_version", "firmware_version", "clock_source",
        "time_source", "master_clock_rate_hz", "sample_rate_hz", "tx_gain_max_db",
        "rx_gain_max_db",
    }
    endpoints = list_value(root.get("endpoints"), "$.endpoints", errors, 3)
    aliases = set()
    alias_keys = set()
    serial_hashes = set()
    role_aliases = {role: set() for role in ROLES}
    for index, value in enumerate(endpoints):
        path = f"$.endpoints[{index}]"
        endpoint = object_value(value, path, endpoint_keys, errors)
        alias = text_value(endpoint, "alias", path, errors)
        role = text_value(endpoint, "role", path, errors)
        for key in (
            "host_alias", "model", "rf_port", "antenna_alias", "backend",
            "driver_version", "firmware_version", "clock_source", "time_source",
        ):
            text_value(endpoint, key, path, errors)
        serial_hash = text_value(endpoint, "serial_hash", path, errors)
        channel = endpoint.get("channel")
        if isinstance(channel, bool) or not isinstance(channel, int) or channel < 0:
            errors.append(f"{path}.channel: must be a non-negative integer")
        for key in ("master_clock_rate_hz", "sample_rate_hz"):
            number_value(endpoint, key, path, errors, 1)
        for key in ("tx_gain_max_db", "rx_gain_max_db"):
            number_value(endpoint, key, path, errors)
        if alias:
            if alias.casefold() in alias_keys:
                errors.append(f"{path}.alias: duplicate endpoint alias")
            aliases.add(alias)
            alias_keys.add(alias.casefold())
        if role not in ROLES:
            errors.append(f"{path}.role: must be one of {sorted(ROLES)}")
        elif alias:
            role_aliases[role].add(alias)
        if serial_hash:
            if not re.fullmatch(r"[0-9a-f]{64}", serial_hash):
                errors.append(f"{path}.serial_hash: must be a lowercase SHA-256")
            elif serial_hash in serial_hashes:
                errors.append(f"{path}.serial_hash: duplicate physical device")
            serial_hashes.add(serial_hash)
    for role, found in role_aliases.items():
        if not found:
            errors.append(f"$.endpoints: missing role {role}")

    path_keys = {
        "alias", "from_endpoint", "to_endpoint", "diagram_ref", "components",
        "total_attenuation_db",
    }
    component_keys = {"alias", "type", "attenuation_db"}
    rf_paths = list_value(root.get("rf_paths"), "$.rf_paths", errors, 2)
    path_aliases = set()
    endpoint_pairs = set()
    for index, value in enumerate(rf_paths):
        path = f"$.rf_paths[{index}]"
        rf_path = object_value(value, path, path_keys, errors)
        alias = text_value(rf_path, "alias", path, errors)
        left = text_value(rf_path, "from_endpoint", path, errors)
        right = text_value(rf_path, "to_endpoint", path, errors)
        text_value(rf_path, "diagram_ref", path, errors)
        total = number_value(rf_path, "total_attenuation_db", path, errors, 0)
        if alias:
            if alias.casefold() in path_aliases:
                errors.append(f"{path}.alias: duplicate RF path alias")
            path_aliases.add(alias.casefold())
        for field, endpoint in (("from_endpoint", left), ("to_endpoint", right)):
            if endpoint and endpoint not in aliases:
                errors.append(f"{path}.{field}: unknown endpoint alias")
        if left and right:
            if left == right:
                errors.append(f"{path}: RF path endpoints must differ")
            endpoint_pairs.add(frozenset((left, right)))
        components = list_value(rf_path.get("components"), f"{path}.components", errors)
        component_aliases = set()
        measured_total = 0.0
        total_known = True
        for component_index, component_value in enumerate(components):
            component_path = f"{path}.components[{component_index}]"
            component = object_value(component_value, component_path, component_keys, errors)
            component_alias = text_value(component, "alias", component_path, errors)
            text_value(component, "type", component_path, errors)
            attenuation = number_value(component, "attenuation_db", component_path, errors, 0)
            if component_alias:
                if component_alias.casefold() in component_aliases:
                    errors.append(f"{component_path}.alias: duplicate component alias in path")
                component_aliases.add(component_alias.casefold())
            if attenuation is None:
                total_known = False
            else:
                measured_total += attenuation
        if total is not None and total_known and abs(total - measured_total) > 0.1:
            errors.append(f"{path}.total_attenuation_db: does not match component sum")
    du_aliases = role_aliases["du"]
    for role in ("attack_ue", "witness_ue"):
        for endpoint in role_aliases[role]:
            if not any(frozenset((du, endpoint)) in endpoint_pairs for du in du_aliases):
                errors.append(f"$.rf_paths: no DU path for {endpoint}")

    leakage_keys = {"threshold", "unit", "instrument_alias", "measurement_location", "procedure_ref"}
    leakage = object_value(root.get("leakage"), "$.leakage", leakage_keys, errors)
    number_value(leakage, "threshold", "$.leakage", errors)
    for key in leakage_keys - {"threshold"}:
        text_value(leakage, key, "$.leakage", errors)

    subscriber_keys = {"attack_alias", "witness_alias", "distinct_profiles"}
    subscribers = object_value(root.get("subscribers"), "$.subscribers", subscriber_keys, errors)
    attack_alias = text_value(subscribers, "attack_alias", "$.subscribers", errors)
    witness_alias = text_value(subscribers, "witness_alias", "$.subscribers", errors)
    true_value(subscribers, "distinct_profiles", "$.subscribers", errors)
    if attack_alias and witness_alias and attack_alias.casefold() == witness_alias.casefold():
        errors.append("$.subscribers: attack and witness aliases must differ")

    witness_keys = {
        "endpoint_alias", "process_host_alias", "independent_sdr",
        "independent_process", "independent_rf_path",
    }
    witness = object_value(root.get("witness"), "$.witness", witness_keys, errors)
    witness_endpoint = text_value(witness, "endpoint_alias", "$.witness", errors)
    text_value(witness, "process_host_alias", "$.witness", errors)
    for key in ("independent_sdr", "independent_process", "independent_rf_path"):
        true_value(witness, key, "$.witness", errors)
    if witness_endpoint and witness_endpoint not in role_aliases["witness_ue"]:
        errors.append("$.witness.endpoint_alias: must reference a witness_ue endpoint")

    approval_keys = {"reviewer_alias", "approved_at"}
    approvals = list_value(root.get("approvals"), "$.approvals", errors, 2)
    reviewers = set()
    for index, value in enumerate(approvals):
        path = f"$.approvals[{index}]"
        approval = object_value(value, path, approval_keys, errors)
        reviewer = text_value(approval, "reviewer_alias", path, errors)
        validate_timestamp(approval.get("approved_at"), f"{path}.approved_at", errors)
        if reviewer:
            reviewer_key = reviewer.casefold()
            if reviewer_key in reviewers:
                errors.append(f"{path}.reviewer_alias: reviewer must be distinct")
            reviewers.add(reviewer_key)
    if len(reviewers) < 2:
        errors.append("$.approvals: needs two distinct reviewers")
    return errors


def main(argv):
    if len(argv) != 1:
        print("usage: validate_ota_inventory.py INVENTORY.json", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(argv[0]).read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"OTA G0 manifest unreadable: {exc}", file=sys.stderr)
        return 1
    errors = validate(data)
    if errors:
        print("OTA G0 manifest invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("OTA G0 manifest structure complete; this command does not prove the physical two-person cross-check, and G1 TX-off is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
