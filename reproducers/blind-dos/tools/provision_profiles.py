#!/usr/bin/env python3
"""Create isolated V/A/C subscriber profiles without changing source files."""

import argparse
import csv
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys


SUBSCRIBER_TARGET = "/open5gs/subscriber_db.csv"
HEX32 = re.compile(r"[0-9a-fA-F]{32}")
IMSI = re.compile(r"[0-9]{15}")
PLMN = re.compile(r"[0-9]{2,3}")
ENV_KEY = re.compile(r"[A-Z][A-Z0-9_]*")


class ProvisionError(ValueError):
    pass


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def fingerprint(value):
    return sha256_bytes(value.encode("utf-8"))


def _input_file(value, label):
    path = Path(value).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ProvisionError(f"{label} must be a regular non-symlink file")
    try:
        return path, path.read_bytes()
    except OSError as exc:
        raise ProvisionError(f"cannot read {label}") from exc


def _one_match(pattern, text, label):
    found = list(pattern.finditer(text))
    if len(found) != 1:
        raise ProvisionError(f"victim config must contain exactly one {label}")
    return found[0]


def parse_oai_config(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvisionError("victim config must be UTF-8") from exc
    if len(re.findall(r"\buicc0\s*=", text)) != 1 \
            or re.search(r"\buicc(?!0\b)[0-9]+\s*=", text):
        raise ProvisionError("victim config must contain only one uicc0 profile")

    values = {}
    patterns = {}
    for name in ("imsi", "key", "opc", "dnn"):
        pattern = re.compile(
            rf"\b{name}\s*=\s*([\"'])([^\"']+)\1\s*;", re.IGNORECASE
        )
        match = _one_match(pattern, text, name)
        values[name] = match.group(2)
        patterns[name] = pattern
    sst = _one_match(
        re.compile(r"\bnssai_sst\s*=\s*([0-9]+)\s*;", re.IGNORECASE),
        text,
        "nssai_sst",
    )
    values["nssai_sst"] = int(sst.group(1))
    pdu_pattern = re.compile(
        r"(?P<prefix>\bpdu_sessions\s*=\s*\(\s*\{)"
        r"(?P<body>[^{}]*)(?P<suffix>\}\s*\)\s*;)",
        re.IGNORECASE | re.DOTALL,
    )
    pdu = _one_match(pdu_pattern, text, "single PDU session")
    pdu_ids = re.findall(r"\bid\s*=\s*([0-9]+)\s*;", pdu.group("body"), re.IGNORECASE)
    if len(pdu_ids) > 1 or (pdu_ids and not 0 <= int(pdu_ids[0]) <= 255):
        raise ProvisionError("PDU session ID must be a single value in 0..255")
    values["pdu_id"] = int(pdu_ids[0]) if pdu_ids and int(pdu_ids[0]) > 0 else 1
    patterns["pdu_session"] = pdu_pattern

    if not IMSI.fullmatch(values["imsi"]):
        raise ProvisionError("victim IMSI must be exactly 15 digits")
    for name in ("key", "opc"):
        if not HEX32.fullmatch(values[name]):
            raise ProvisionError(f"victim {name} must be exactly 32 hexadecimal digits")
    if values["dnn"] != "internet" or values["nssai_sst"] != 1:
        raise ProvisionError("victim config must use DNN internet and NSSAI SST 1")
    return text, values, patterns


def parse_env(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProvisionError("Open5GS env must be UTF-8") from exc
    lines = text.splitlines(keepends=True)
    values = {}
    positions = {}
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if not body.strip() or body.lstrip().startswith("#") or "=" not in body:
            continue
        key, value = body.split("=", 1)
        key = key.strip()
        if not ENV_KEY.fullmatch(key):
            raise ProvisionError("Open5GS env contains an invalid key")
        if key in values:
            raise ProvisionError(f"Open5GS env contains duplicate {key}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
        positions[key] = index

    required = ("SUBSCRIBER_DB", "MCC", "MNC", "UE_IP_BASE")
    if any(key not in values for key in required):
        raise ProvisionError("Open5GS env is missing a required provisioning key")
    fields = values["SUBSCRIBER_DB"].split(",")
    if len(fields) != 7 or any(not field for field in fields):
        raise ProvisionError("SUBSCRIBER_DB must be one inline seven-field profile")
    imsi, key, op_type, opc, amf, qci, ip_alloc = fields
    if not IMSI.fullmatch(imsi) or not HEX32.fullmatch(key) or not HEX32.fullmatch(opc):
        raise ProvisionError("SUBSCRIBER_DB has an invalid subscriber credential schema")
    if op_type.lower() != "opc" or not re.fullmatch(r"[0-9a-fA-F]{4}", amf):
        raise ProvisionError("SUBSCRIBER_DB must use OPC and a four-hex-digit AMF")
    try:
        qci_value = int(qci)
        ip_value = ipaddress.IPv4Address(ip_alloc)
    except ValueError as exc:
        raise ProvisionError("SUBSCRIBER_DB has an invalid QCI or IPv4 address") from exc
    if not 1 <= qci_value <= 255:
        raise ProvisionError("SUBSCRIBER_DB QCI must be in 1..255")
    if not re.fullmatch(r"[0-9]{3}", values["MCC"]) or not PLMN.fullmatch(values["MNC"]):
        raise ProvisionError("MCC/MNC must be three and two-or-three decimal digits")
    prefix = values["MCC"] + values["MNC"]
    if not imsi.startswith(prefix) or len(prefix) >= 15:
        raise ProvisionError("victim IMSI does not match MCC/MNC")

    base = values["UE_IP_BASE"]
    try:
        if re.fullmatch(r"(?:[0-9]{1,3}\.){2}[0-9]{1,3}", base):
            base_address = ipaddress.IPv4Address(base + ".0")
            if base_address.packed[2] != 0:
                raise ValueError
            network = ipaddress.IPv4Network(base + ".0/16")
        else:
            network = ipaddress.IPv4Network(base, strict=False)
    except ValueError as exc:
        raise ProvisionError("UE_IP_BASE must identify an IPv4 network") from exc
    if ip_value not in network:
        raise ProvisionError("victim IP must be inside the UE_IP_BASE network")
    victim_24 = ipaddress.IPv4Network(f"{ip_value}/24", strict=False)
    allocation_network = victim_24 if victim_24.subnet_of(network) else network
    if ip_value in {allocation_network.network_address,
                    allocation_network.broadcast_address,
                    allocation_network.network_address + 1}:
        raise ProvisionError("victim IP must be a usable non-gateway address")
    return text, lines, values, positions, fields, allocation_network


def _replace_oai(text, patterns, replacements):
    result = text
    for name in ("imsi", "key", "opc"):
        pattern = patterns[name]
        value = replacements[name]
        result, count = pattern.subn(
            lambda match: match.group(0).replace(match.group(2), value, 1),
            result,
        )
        if count != 1:
            raise ProvisionError(f"failed to replace exactly one {name}")
    pdu_id = replacements["pdu_id"]
    id_pattern = re.compile(r"\bid\s*=\s*[0-9]+\s*;", re.IGNORECASE)

    def replace_pdu(match):
        body, count = id_pattern.subn(f"id={pdu_id};", match.group("body"))
        if count == 0:
            body = f" id={pdu_id};" + body
        return match.group("prefix") + body + match.group("suffix")

    result, count = patterns["pdu_session"].subn(replace_pdu, result)
    if count != 1:
        raise ProvisionError("failed to set exactly one PDU session ID")
    parsed = parse_oai_config(result.encode("utf-8"))[1]
    if any(parsed[name].lower() != replacements[name].lower()
           for name in ("imsi", "key", "opc")):
        raise ProvisionError("generated OAI profile did not round-trip")
    if parsed["pdu_id"] != pdu_id:
        raise ProvisionError("generated PDU session ID did not round-trip")
    return result.encode("utf-8")


def _new_imsi(prefix, used):
    width = 15 - len(prefix)
    for _ in range(1024):
        value = prefix + f"{secrets.randbelow(10 ** width):0{width}d}"
        if value not in used:
            used.add(value)
            return value
    raise ProvisionError("could not generate a unique IMSI")


def _new_hex(used):
    for _ in range(1024):
        value = secrets.token_hex(16)
        if value not in used:
            used.add(value)
            return value
    raise ProvisionError("could not generate a unique subscriber secret")


def _free_ips(network, victim_ip):
    gateway = network.network_address + 1
    excluded = {network.network_address, network.broadcast_address, gateway, victim_ip}
    free = [address for address in network.hosts() if address not in excluded]
    if len(free) < 2:
        raise ProvisionError("UE_IP_BASE does not have two free subscriber addresses")
    return free[:2]


def _rewrite_env(lines, position):
    output = list(lines)
    original = output[position]
    newline = "\r\n" if original.endswith("\r\n") else "\n" if original.endswith("\n") else ""
    indent = original[:len(original) - len(original.lstrip())]
    output[position] = f"{indent}SUBSCRIBER_DB={SUBSCRIBER_TARGET}{newline}"
    return "".join(output).encode("utf-8")


def _validate_csv(data, profiles):
    try:
        rows = list(csv.reader(data.decode("utf-8").splitlines()))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ProvisionError("generated subscriber CSV is invalid") from exc
    if len(rows) != 3 or any(len(row) != 8 for row in rows):
        raise ProvisionError("subscriber CSV must contain exactly three eight-field rows")
    if any(not row[0].startswith("blind-") for row in rows):
        raise ProvisionError("subscriber CSV must not contain a header")
    for index, profile in enumerate(profiles):
        expected = [
            f"blind-{profile['role']}", profile["imsi"], profile["key"], "opc",
            profile["opc"], profile["amf"], str(profile["qci"]), profile["ip"],
        ]
        if rows[index] != expected:
            raise ProvisionError("subscriber CSV did not round-trip")
    for field in ("imsi", "key", "opc", "ip"):
        if len({profile[field].lower() for profile in profiles}) != 3:
            raise ProvisionError(f"generated profiles do not have unique {field} values")


def build_outputs(victim_data, env_data, mount_source):
    victim_text, victim, patterns = parse_oai_config(victim_data)
    _, env_lines, env_values, env_positions, fields, network = parse_env(env_data)
    imsi, key, _, opc, amf, qci, ip_alloc = fields
    if (victim["imsi"] != imsi or victim["key"].lower() != key.lower()
            or victim["opc"].lower() != opc.lower()):
        raise ProvisionError("victim OAI profile does not match Open5GS SUBSCRIBER_DB")
    if victim["pdu_id"] != 1:
        raise ProvisionError("victim PDU session ID must be absent, 0, or 1")

    prefix = env_values["MCC"] + env_values["MNC"]
    used_imsi = {imsi}
    used_secret = {key.lower(), opc.lower()}
    attacker_imsi = _new_imsi(prefix, used_imsi)
    control_imsi = _new_imsi(prefix, used_imsi)
    attacker_key = _new_hex(used_secret)
    attacker_opc = _new_hex(used_secret)
    control_key = _new_hex(used_secret)
    control_opc = _new_hex(used_secret)
    attacker_ip, control_ip = _free_ips(network, ipaddress.IPv4Address(ip_alloc))

    profiles = [
        {"role": "victim", "imsi": imsi, "key": key, "opc": opc,
         "amf": amf, "qci": int(qci), "ip": ip_alloc, "pdu_id": 1},
        {"role": "attacker", "imsi": attacker_imsi, "key": attacker_key,
         "opc": attacker_opc, "amf": amf, "qci": int(qci), "ip": str(attacker_ip), "pdu_id": 2},
        {"role": "control", "imsi": control_imsi, "key": control_key,
         "opc": control_opc, "amf": amf, "qci": int(qci), "ip": str(control_ip), "pdu_id": 3},
    ]

    outputs = {
        "victim.conf": _replace_oai(victim_text, patterns, profiles[0]),
        "attacker.conf": _replace_oai(victim_text, patterns, profiles[1]),
        "control.conf": _replace_oai(victim_text, patterns, profiles[2]),
    }
    csv_text = "".join(
        ",".join([
            f"blind-{profile['role']}", profile["imsi"], profile["key"], "opc",
            profile["opc"], profile["amf"], str(profile["qci"]), profile["ip"],
        ]) + "\n"
        for profile in profiles
    ).encode("utf-8")
    _validate_csv(csv_text, profiles)
    outputs["subscriber_db.csv"] = csv_text
    outputs["open5gs.env"] = _rewrite_env(env_lines, env_positions["SUBSCRIBER_DB"])
    outputs["compose.override.yml"] = (
        "services:\n"
        "  5gc:\n"
        "    volumes:\n"
        "      - type: bind\n"
        f"        source: {json.dumps(str(mount_source))}\n"
        f"        target: {SUBSCRIBER_TARGET}\n"
        "        read_only: true\n"
    ).encode("utf-8")

    manifest = {
        "schema_version": "blind.profile-provision.v1",
        "profile_count": 3,
        "compose_mount_source": str(mount_source),
        "sources": {
            "victim_config_sha256": sha256_bytes(victim_data),
            "open5gs_env_sha256": sha256_bytes(env_data),
        },
        "profiles": [
            {
                "role": profile["role"],
                "imsi_sha256": fingerprint(profile["imsi"]),
                "key_sha256": fingerprint(profile["key"].lower()),
                "opc_sha256": fingerprint(profile["opc"].lower()),
                "ip_sha256": fingerprint(profile["ip"]),
                "pdu_session_id": profile["pdu_id"],
                "ue_config_sha256": sha256_bytes(outputs[f"{profile['role']}.conf"]),
            }
            for profile in profiles
        ],
        "files": {name: sha256_bytes(data) for name, data in sorted(outputs.items())},
    }
    outputs["profiles.manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return outputs


def _write_private(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            fd = -1
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(path, 0o600, follow_symlinks=False)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    finally:
        if fd >= 0:
            os.close(fd)


def provision(victim_path, env_path, output_dir, compose_mount_source=None):
    victim_path, victim_data = _input_file(victim_path, "victim config")
    env_path, env_data = _input_file(env_path, "Open5GS env")
    del victim_path, env_path

    output = Path(os.path.abspath(os.path.expanduser(str(output_dir))))
    if os.path.lexists(output):
        raise ProvisionError("output directory must not already exist")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ProvisionError("output parent must be a regular non-symlink directory")
    if compose_mount_source is None:
        mount_source = output / "subscriber_db.csv"
    else:
        requested = Path(os.path.expanduser(str(compose_mount_source)))
        if not requested.is_absolute() or requested.is_symlink() or requested.is_dir():
            raise ProvisionError("compose mount source must be an absolute non-directory path")
        mount_source = Path(os.path.abspath(requested))

    outputs = build_outputs(victim_data, env_data, mount_source)
    created = []
    old_umask = os.umask(0o077)
    try:
        os.mkdir(output, 0o700)
        os.chmod(output, 0o700, follow_symlinks=False)
        for name, data in outputs.items():
            path = output / name
            _write_private(path, data)
            created.append(path)
        if stat.S_IMODE(output.stat(follow_symlinks=False).st_mode) != 0o700:
            raise ProvisionError("output directory permissions are not 0700")
        for path in created:
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
                raise ProvisionError("output file permissions are not 0600")
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        try:
            output.rmdir()
        except OSError:
            pass
        raise
    finally:
        os.umask(old_umask)
    manifest_hash = sha256_bytes((output / "profiles.manifest.json").read_bytes())
    return output, manifest_hash


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--victim-config", required=True)
    parser.add_argument("--open5gs-env", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--compose-mount-source",
        help="absolute deployed CSV path; defaults to OUTPUT_DIR/subscriber_db.csv",
    )
    args = parser.parse_args(argv)
    try:
        output, manifest_hash = provision(
            args.victim_config,
            args.open5gs_env,
            args.output_dir,
            args.compose_mount_source,
        )
    except (OSError, ProvisionError) as exc:
        print(f"provision_profiles: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "manifest_sha256": manifest_hash,
        "output_dir": str(output),
        "profile_count": 3,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
