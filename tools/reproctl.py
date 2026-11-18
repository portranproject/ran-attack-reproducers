#!/usr/bin/env python3
"""공통 재현 카탈로그, 프로필, 탐지 재생과 증거 봉인을 관리한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPRODUCERS = ROOT / "reproducers"
PROFILE_DIR = Path(os.environ.get("RAN_REPRO_PROFILE_DIR", ROOT / "profiles"))
DEFAULT_RUN_ROOT = Path(os.environ.get("RAN_REPRO_RUN_ROOT", ROOT / "runs"))
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
LEVELS = {
    "protocol",
    "protocol-result-emulation",
    "protocol-observation-emulation",
    "detector-input-emulation",
}
STATUSES = {"pass", "fail", "not_observed", "not_applicable", "inconclusive"}
REQUIRED_FILES = (
    "run.json",
    "observations.jsonl",
    "oracle.jsonl",
    "detector.jsonl",
    "verdict.json",
    "report.md",
)


class ReproError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise ReproError(f"Git 확인 실패: {result.stderr.strip() or 'unknown error'}")
    return result


def regular(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ReproError(f"{label}이 일반 파일이 아닙니다: {path}")
    return path


def directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ReproError(f"{label}이 실제 디렉터리가 아닙니다: {path}")
    return path


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReproError(f"{label} JSON이 잘못됐습니다: {error}") from error
    if not isinstance(value, dict):
        raise ReproError(f"{label}은 JSON 객체여야 합니다: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise ReproError(f"기존 파일은 덮어쓰지 않습니다: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with regular(path, path.name).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_qualified_checkout(root: Path = ROOT) -> str:
    lock = load_object(root / "integration.lock.json", "integration lock")
    qualification = lock.get("reproducer")
    if not isinstance(qualification, dict):
        raise ReproError("integration lock에 재현도구 자격 정보가 없습니다")
    minimum = str(qualification.get("minimum_commit", ""))
    required = qualification.get("required_files")
    if not COMMIT.fullmatch(minimum) or not isinstance(required, dict) or not required:
        raise ReproError("integration lock의 재현도구 자격 정보가 잘못됐습니다")
    if git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        raise ReproError("Git 없는 복사본은 자격 실행에 사용할 수 없습니다. 저장소를 clone하세요")
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    if git(root, "merge-base", "--is-ancestor", minimum, head, check=False).returncode != 0:
        raise ReproError(f"재현도구가 자격 기준보다 오래됐습니다: {head}")
    dirty = git(root, "status", "--porcelain=v1", "--untracked-files=no").stdout.strip()
    if dirty:
        raise ReproError("재현도구의 추적 파일이 수정됐습니다. clean checkout이 필요합니다")
    for relative, expected in required.items():
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ReproError("integration lock의 필수 파일 경로가 잘못됐습니다")
        if not SHA256.fullmatch(str(expected)):
            raise ReproError(f"integration lock의 SHA-256이 잘못됐습니다: {relative}")
        path = regular(root / relative, f"자격 필수 파일 {relative}")
        if sha256(path) != expected:
            raise ReproError(f"자격 필수 파일 해시가 다릅니다: {relative}")
    return head


def validate_manifest(value: dict[str, Any], path: Path) -> None:
    required = {
        "schema", "id", "module", "name", "rule_ids", "reproduction_level", "active_mode",
        "claim", "commands", "environments", "detection", "safety", "provenance",
    }
    missing = required - value.keys()
    if missing:
        raise ReproError(f"manifest 필드가 없습니다({','.join(sorted(missing))}): {path}")
    if value["schema"] != "ran-reproducer.module.v1":
        raise ReproError(f"manifest schema가 다릅니다: {path}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", value["id"]):
        raise ReproError(f"manifest id가 잘못됐습니다: {path}")
    if value["reproduction_level"] not in LEVELS or value["active_mode"] not in {"attack", "emulation"}:
        raise ReproError(f"재현 수준 또는 active_mode가 잘못됐습니다: {path}")
    rules = value["rule_ids"]
    if not isinstance(rules, list) or not rules or len(set(rules)) != len(rules) or not all(isinstance(x, str) and x for x in rules):
        raise ReproError(f"rule_ids가 잘못됐습니다: {path}")
    commands = value["commands"]
    if not isinstance(commands, dict) or not isinstance(commands.get("run"), str):
        raise ReproError(f"run command가 없습니다: {path}")
    if value["module"] != path.parent.name:
        raise ReproError(f"manifest module과 디렉터리가 다릅니다: {path}")
    for name, command in commands.items():
        if not isinstance(command, str) or not command:
            raise ReproError(f"빈 command입니다({name}): {path}")
        if command.startswith("@"):
            continue
        entry = path.parent / shlex.split(command)[0]
        if not entry.is_file() or entry.is_symlink():
            raise ReproError(f"command 진입점이 없습니다({name}): {entry}")
    if commands["run"] == "@common-signal" and not isinstance(value.get("signal_generator"), str):
        raise ReproError(f"공통 입력 generator가 없습니다: {path}")
    envs = value["environments"]
    if not isinstance(envs, dict) or set(envs) != {"p5", "ota"} or any(x not in {"qualified", "pending", "not-applicable"} for x in envs.values()):
        raise ReproError(f"p5/ota 환경 상태가 잘못됐습니다: {path}")
    detection = value["detection"]
    if not isinstance(detection, dict) or detection.get("period_ms") != 100 or detection.get("expected_rule") not in rules:
        raise ReproError(f"탐지 계약이 잘못됐습니다: {path}")
    safety = value["safety"]
    if not isinstance(safety, dict) or safety.get("requires_enable") is not True:
        raise ReproError(f"안전 게이트가 없습니다: {path}")
    provenance = value["provenance"]
    refs = provenance.get("references") if isinstance(provenance, dict) else None
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) and x.startswith(("https://", "http://")) for x in refs):
        raise ReproError(f"고정 참조 URL이 없습니다: {path}")


def manifests() -> list[tuple[Path, dict[str, Any]]]:
    found: list[tuple[Path, dict[str, Any]]] = []
    ids: dict[str, Path] = {}
    aliases: dict[str, Path] = {}
    for path in sorted(REPRODUCERS.glob("*/reproducer.json")):
        value = load_object(path, "manifest")
        validate_manifest(value, path)
        scenario_id = value["id"]
        if scenario_id in ids:
            raise ReproError(f"중복 scenario id입니다: {scenario_id}")
        ids[scenario_id] = path
        for alias in value.get("aliases", []):
            if not isinstance(alias, str) or alias in ids or alias in aliases:
                raise ReproError(f"중복 또는 잘못된 alias입니다: {alias}")
            aliases[alias] = path
        found.append((path, value))
    if not found:
        raise ReproError("reproducer.json을 찾지 못했습니다")
    return found


def resolve_manifest(name: str) -> tuple[Path, dict[str, Any]]:
    for path, value in manifests():
        if name == value["id"] or name in value.get("aliases", []):
            return path, value
    raise ReproError(f"알 수 없는 재현 시나리오입니다: {name}")


def profile_path(name: str) -> Path:
    given = Path(name)
    if given.is_absolute() or "/" in name:
        return given
    return PROFILE_DIR / f"{name}.json"


def validate_profile(value: dict[str, Any], path: Path, require_ready: bool) -> None:
    required = {
        "schema", "id", "backend", "configured", "lab_only", "run_root", "environment",
        "detector", "telemetry", "limits", "target_allowlist",
    }
    missing = required - value.keys()
    if missing:
        raise ReproError(f"profile 필드가 없습니다({','.join(sorted(missing))}): {path}")
    if value["schema"] != "ran-reproducer.profile.v1" or value["backend"] not in {"p5", "ota", "replay"}:
        raise ReproError(f"profile schema/backend가 잘못됐습니다: {path}")
    if not isinstance(value["id"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value["id"]):
        raise ReproError(f"profile id가 잘못됐습니다: {path}")
    if value["lab_only"] is not True:
        raise ReproError("lab_only=true인 격리 환경만 허용합니다")
    if require_ready and value["configured"] is not True:
        raise ReproError(f"profile이 아직 예제 상태입니다: {path}")
    environment = value["environment"]
    if not isinstance(environment, dict) or any(not ENV_NAME.fullmatch(k) or not isinstance(v, str) or "\n" in v for k, v in environment.items()):
        raise ReproError("profile environment가 잘못됐습니다")
    detector = value["detector"]
    telemetry = value["telemetry"]
    for label, component in (("detector", detector), ("telemetry", telemetry)):
        if not isinstance(component, dict) or not COMMIT.fullmatch(str(component.get("commit", ""))):
            raise ReproError(f"{label} 고정 commit이 잘못됐습니다")
    if telemetry.get("period_ms") != 100:
        raise ReproError("telemetry period_ms는 100이어야 합니다")
    limits = value["limits"]
    if not isinstance(limits, dict) or not 1 <= int(limits.get("max_duration_s", 0)) <= 3600 or not 1 <= int(limits.get("max_ues", 0)) <= 256:
        raise ReproError("profile 실행 상한이 잘못됐습니다")
    allowlist = value["target_allowlist"]
    if not isinstance(allowlist, list) or not allowlist or any(not isinstance(x, str) or not x for x in allowlist):
        raise ReproError("target_allowlist가 비었습니다")
    if value["backend"] == "ota":
        rf = value.get("rf")
        if not isinstance(rf, dict):
            raise ReproError("OTA profile에는 rf inventory가 필요합니다")
        if require_ready and rf.get("shielding_confirmed") is not True:
            raise ReproError("차폐 확인 전에는 OTA profile을 사용할 수 없습니다")
        devices = rf.get("devices")
        if not isinstance(devices, list) or len(devices) < 2 or any(not x.get("serial") for x in devices if isinstance(x, dict)):
            raise ReproError("OTA SDR inventory가 불완전합니다")
    if require_ready and value["backend"] == "p5":
        required_hosts = {"P5_CU_HOST", "P5_DU_HOST", "P5_CU_PRIVATE_IP", "P5_DU_PRIVATE_IP"}
        if required_hosts - environment.keys() or any(environment[key].startswith("replace-with-") for key in required_hosts):
            raise ReproError("p5 CU/DU endpoint가 불완전합니다")


def load_profile(name: str, require_ready: bool = True) -> tuple[Path, dict[str, Any]]:
    path = profile_path(name)
    if not path.exists():
        example = path.with_name(path.stem + ".example.json")
        hint = f" 예제를 복사해 검토하세요: {example}" if example.exists() else ""
        raise ReproError(f"profile이 없습니다: {path}.{hint}")
    value = load_object(path, "profile")
    validate_profile(value, path, require_ready)
    return path, value


def check_private_credentials(profile: dict[str, Any]) -> None:
    raw = profile.get("credentials_file")
    if raw is None:
        return
    path = regular(Path(raw), "credentials_file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ReproError(f"credentials_file 권한은 0600 이하여야 합니다: {path}")


def env_file(path: Path, label: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, source in enumerate(regular(path, label).read_text(encoding="utf-8").splitlines(), 1):
        line = source.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ReproError(f"{label}:{number}는 NAME=VALUE 형식이어야 합니다")
        name, encoded = line.split("=", 1)
        if not ENV_NAME.fullmatch(name):
            raise ReproError(f"{label}:{number} 변수명이 잘못됐습니다")
        try:
            tokens = shlex.split(encoded, comments=True, posix=True)
        except ValueError as error:
            raise ReproError(f"{label}:{number} 값이 잘못됐습니다: {error}") from error
        if len(tokens) != 1 or "\n" in tokens[0]:
            raise ReproError(f"{label}:{number} 값은 하나여야 합니다")
        values[name] = tokens[0]
    return values


def private_credentials(profile: dict[str, Any]) -> dict[str, str]:
    check_private_credentials(profile)
    raw = profile.get("credentials_file")
    return {} if raw is None else env_file(Path(raw), "credentials_file")


def live_e2e_settings(profile: dict[str, Any]) -> dict[str, str]:
    environment = profile["environment"]
    conf = Path(environment.get("LIVE_E2E_CONF", "/root/live-e2e.conf"))
    if not conf.is_absolute():
        raise ReproError("LIVE_E2E_CONF는 절대 경로여야 합니다")
    mode = stat.S_IMODE(regular(conf, "LIVE_E2E_CONF").stat().st_mode)
    if mode & 0o077:
        raise ReproError(f"LIVE_E2E_CONF 권한은 0600 이하여야 합니다: {conf}")
    settings = env_file(conf, "LIVE_E2E_CONF")
    for name in ("CU_PLATFORM_ROOT", "CU_DASHBOARD_ENV", "CU_TELEMETRY_NODE"):
        if name in environment:
            settings[name] = environment[name]
    required = {
        "CU_HOST", "SSH_KEY", "KNOWN_HOSTS", "CU_PLATFORM_ROOT", "CU_LIVE_RUN_ROOT",
        "CU_F1_INTERFACE", "CU_N2_INTERFACE", "CU_DASHBOARD_URL", "CU_DASHBOARD_CA_FILE",
        "CU_DASHBOARD_ENV", "CU_TELEMETRY_NODE",
    }
    missing = required - settings.keys()
    if missing:
        raise ReproError(f"LIVE_E2E 설정이 없습니다({','.join(sorted(missing))}): {conf}")
    for name in ("CU_PLATFORM_ROOT", "CU_LIVE_RUN_ROOT", "CU_DASHBOARD_CA_FILE", "SSH_KEY", "KNOWN_HOSTS"):
        if not Path(settings[name]).is_absolute() or Path(settings[name]) == Path("/"):
            raise ReproError(f"{name}은 안전한 절대 경로여야 합니다")
    if settings["CU_HOST"] != environment.get("P5_CU_HOST"):
        raise ReproError("LIVE_E2E CU_HOST와 profile P5_CU_HOST가 다릅니다")
    if not settings["CU_DASHBOARD_URL"].startswith("https://"):
        raise ReproError("CU_DASHBOARD_URL은 https여야 합니다")
    for name in ("CU_DASHBOARD_ENV", "CU_TELEMETRY_NODE"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", settings[name]):
            raise ReproError(f"{name} 라벨이 잘못됐습니다")
    platform = Path(settings["CU_PLATFORM_ROOT"])
    expected = {
        "detector binary": platform / "detection/build/detector",
        "detector config": platform / "detection/config/detector.json",
        "telemetry binary": platform / "telemetry/build/portran",
    }
    actual = {
        "detector binary": Path(profile["detector"]["binary"]),
        "detector config": Path(profile["detector"]["config"]),
        "telemetry binary": Path(profile["telemetry"]["binary"]),
    }
    for label, path in expected.items():
        if actual[label] != path:
            raise ReproError(f"profile {label}과 LIVE_E2E 실행 경로가 다릅니다: {actual[label]} != {path}")
    return settings


def p5_remote_components(profile: dict[str, Any]) -> dict[str, str]:
    environment = profile["environment"]
    credentials = private_credentials(profile)
    live = live_e2e_settings(profile)
    host = environment.get("P5_CU_HOST", "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*@[A-Za-z0-9.-]+", host):
        raise ReproError("P5_CU_HOST는 user@host 형식이어야 합니다")
    key = regular(Path(credentials.get("SSH_KEY", "")), "SSH_KEY")
    known_hosts = regular(Path(credentials.get("KNOWN_HOSTS", "")), "KNOWN_HOSTS")
    if Path(live["SSH_KEY"]) != key or Path(live["KNOWN_HOSTS"]) != known_hosts:
        raise ReproError("LIVE_E2E와 profile credentials의 SSH 경로가 다릅니다")
    if stat.S_IMODE(key.stat().st_mode) & 0o077:
        raise ReproError(f"SSH_KEY 권한은 0600 이하여야 합니다: {key}")
    detector = profile["detector"]
    telemetry = profile["telemetry"]
    paths = {
        "detector": detector["binary"],
        "detector_config": detector["config"],
        "telemetry": telemetry["binary"],
        "dashboard_sender": str(Path(live["CU_PLATFORM_ROOT"]) / "detection/tools/dashboard_sender.py"),
        "dashboard_ca": live["CU_DASHBOARD_CA_FILE"],
    }
    if any(not Path(value).is_absolute() for value in paths.values()):
        raise ReproError("p5 production component 경로는 절대 경로여야 합니다")
    payload = {
        "paths": paths,
        "detector_commit": detector["commit"],
        "telemetry_commit": telemetry["commit"],
    }
    remote = r'''import hashlib,json,os,pathlib,shutil,sys
request=json.loads(sys.argv[1]); result={}
for command in ("tcpdump","tshark"):
    if shutil.which(command) is None: raise SystemExit(f"missing CU capture command: {command}")
for name,raw in request["paths"].items():
    path=pathlib.Path(raw)
    if path.is_symlink() or not path.is_file(): raise SystemExit(f"missing production component: {name}")
    if name in ("detector","telemetry") and not os.access(path, os.X_OK): raise SystemExit(f"component is not executable: {name}")
    result[name+"_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
for name,expected in (("detector",request["detector_commit"]),("telemetry",request["telemetry_commit"])):
    revision=pathlib.Path(request["paths"][name]).parent.parent/".deployed-revision"
    if revision.is_symlink() or not revision.is_file() or revision.read_text().strip()!=expected:
        raise SystemExit(f"deployed revision mismatch: {name}")
print(json.dumps(result,sort_keys=True))'''
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=yes",
         "-o", f"UserKnownHostsFile={known_hosts}", "-i", str(key), host,
         shlex.join(["python3", "-c", remote, json.dumps(payload, separators=(",", ":"))])],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ReproError(f"CU production component 확인 실패: {result.stderr.strip() or 'unknown error'}")
    try:
        verified = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReproError("CU production component 응답이 JSON이 아닙니다") from error
    expected = {"detector_sha256", "detector_config_sha256", "telemetry_sha256",
                "dashboard_sender_sha256", "dashboard_ca_sha256"}
    if set(verified) != expected or any(not SHA256.fullmatch(str(verified[name])) for name in expected):
        raise ReproError("CU production component 해시 응답이 잘못됐습니다")
    return {name: str(value) for name, value in verified.items()}


def detector_paths(profile: dict[str, Any]) -> tuple[Path, Path]:
    detector = profile["detector"]
    binary = regular(Path(os.environ.get("DETECTOR_BIN", detector["binary"])), "detector binary")
    config = regular(Path(os.environ.get("DETECTOR_CONFIG", detector["config"])), "detector config")
    if not os.access(binary, os.X_OK):
        raise ReproError(f"detector binary가 실행 가능하지 않습니다: {binary}")
    return binary, config


def run_root(profile: dict[str, Any] | None = None) -> Path:
    root = Path(os.environ.get("RAN_REPRO_RUN_ROOT", profile["run_root"] if profile else DEFAULT_RUN_ROOT))
    if root == Path("/") or root.is_symlink():
        raise ReproError(f"안전하지 않은 run root입니다: {root}")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory(root, "run root")


def parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(regular(path, path.name).read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ReproError(f"{path.name}:{number} JSON이 잘못됐습니다: {error}") from error
        if not isinstance(row, dict):
            raise ReproError(f"{path.name}:{number} JSON 객체가 아닙니다")
        rows.append(row)
    if not rows:
        raise ReproError(f"빈 JSONL입니다: {path}")
    return rows


def validate_observations(path: Path, expected_period_ms: int = 100) -> dict[str, Any]:
    rows = parse_jsonl(path)
    hello = next((row for row in rows if row.get("type") == "hello"), None)
    if not hello or hello.get("period_ms") != expected_period_ms or hello.get("ue_evt") is not True:
        raise ReproError("hello의 period_ms=100·ue_evt=true를 확인하지 못했습니다")
    if any(row.get("type") == "gap" for row in rows):
        raise ReproError("입력에 gap이 있어 탐지 판정을 할 수 없습니다")
    seqs = [row.get("seq") for row in rows]
    if any(not isinstance(seq, int) for seq in seqs) or seqs != list(range(1, len(rows) + 1)):
        raise ReproError("입력 seq가 1부터 연속 증가하지 않습니다")
    times = [row["t_ms"] for row in rows if row.get("type") == "ue_evt" and isinstance(row.get("t_ms"), int)]
    if times != sorted(times):
        raise ReproError("ue_evt t_ms가 역행합니다")
    windows = [row for row in rows if row.get("type") == "kpm2"]
    if any(row.get("t_end_ms", 0) - row.get("t_start_ms", 0) != expected_period_ms for row in windows):
        raise ReproError("kpm2 period가 hello와 다릅니다")
    return {"rows": len(rows), "ue_events": len(times), "first_t_ms": min(times) if times else None, "last_t_ms": max(times) if times else None}


def detector_alerts(binary: Path, config: Path, observations: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="ran-detector-") as directory_name:
        result = subprocess.run(
            [str(binary), "--replay", str(observations), "--speed", "max", "--config", str(config)],
            cwd=directory_name,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    if result.returncode != 0:
        raise ReproError(f"detector replay 실패(rc={result.returncode}): {result.stderr.strip()}")
    alerts: list[dict[str, Any]] = []
    for stream, content in (("stdout", result.stdout), ("stderr", result.stderr)):
        for line in content.splitlines():
            if not line.startswith("ALERT "):
                continue
            tokens = shlex.split(line)
            row: dict[str, Any] = {"schema": "ran-reproducer.detector-event.v1", "stream": stream, "raw": line}
            if len(tokens) > 1:
                row["action"] = tokens[1]
            for token in tokens[2:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    row[key] = value
            alerts.append(row)
    metadata = {
        "binary_sha256": sha256(binary),
        "config_sha256": sha256(config),
        "stdout_lines": len(result.stdout.splitlines()),
        "stderr_lines": len(result.stderr.splitlines()),
    }
    return alerts, metadata


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists() or path.is_symlink():
        raise ReproError(f"기존 파일은 덮어쓰지 않습니다: {path}")
    with path.open("x", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def load_signal_generator():
    sys.path.insert(0, str(ROOT / "tools"))
    from generate_rule_signal import generate  # pylint: disable=import-outside-toplevel
    return generate


def report_text(run: dict[str, Any], verdict: dict[str, Any], input_stats: dict[str, Any], detector_meta: dict[str, Any]) -> str:
    dimensions = verdict["dimensions"]
    return (
        f"# 재현 실행 {run['run_id']}\n\n"
        f"- 시나리오: `{run['scenario_id']}`\n"
        f"- 탐지 룰: `{verdict['expected_rule']}`\n"
        f"- 실행 모드: `{run['mode']}`\n"
        f"- 재현 수준: `{run['reproduction_level']}`\n"
        f"- 전체 판정: `{'pass' if verdict['passed'] else 'fail'}`\n"
        f"- 기전: `{dimensions['mechanism']}`\n"
        f"- 탐지 입력: `{dimensions['detection_input']}`\n"
        f"- 탐지 결과: `{dimensions['detector_result']}`\n"
        f"- 서비스 영향: `{dimensions['service_impact']}`\n\n"
        "## 입력과 탐지\n\n"
        f"- 입력 행: {input_stats['rows']}\n"
        f"- UE 이벤트: {input_stats['ue_events']}\n"
        f"- 예상 룰 RAISE: {verdict['observed_alerts']}건\n"
        f"- 탐지 지연: {verdict.get('detection_latency_ms') if verdict.get('detection_latency_ms') is not None else '채점 안 함'} ms\n"
        f"- detector SHA-256: `{detector_meta['binary_sha256']}`\n"
        f"- detector config SHA-256: `{detector_meta['config_sha256']}`\n\n"
        "## 주장 경계\n\n"
        f"- live protocol path observed: `{str(run['claims']['live_protocol_path_observed']).lower()}`\n"
        f"- RF cause observed: `{str(run['claims']['rf_cause_observed']).lower()}`\n"
        f"- service denial observed: `{str(run['claims']['service_denial_observed']).lower()}`\n"
    )


def seal(run_dir: Path, run_id: str) -> dict[str, Any]:
    files = {}
    for name in REQUIRED_FILES:
        path = regular(run_dir / name, name)
        files[name] = {"size": path.stat().st_size, "sha256": sha256(path)}
    value = {"schema": "ran-reproducer.evidence.v1", "run_id": run_id, "files": files}
    write_json(run_dir / "evidence_manifest.json", value)
    return value


def command_seal(run_dir_value: str, run_id: str) -> None:
    if not RUN_ID.fullmatch(run_id):
        raise ReproError("RUN_ID가 잘못됐습니다")
    run_dir = Path(run_dir_value)
    if run_dir.is_symlink() or not run_dir.is_dir() or run_dir.name != run_id:
        raise ReproError("봉인할 실행 디렉터리가 RUN_ID와 맞지 않습니다")
    seal(run_dir, run_id)
    print(f"sealed: {run_dir}")


def signal_run(scenario_name: str, mode: str, run_id_value: str, profile_name: str, enabled: bool) -> Path:
    if not RUN_ID.fullmatch(run_id_value):
        raise ReproError("RUN_ID는 영문·숫자로 시작하고 ._-만 사용할 수 있습니다")
    manifest_path, manifest = resolve_manifest(scenario_name)
    expected_mode = manifest["active_mode"]
    if mode not in {"control", expected_mode}:
        raise ReproError(f"mode는 control 또는 {expected_mode}이어야 합니다")
    if mode == "control" and enabled:
        raise ReproError("control에는 --enable을 붙이지 않습니다")
    if mode != "control" and not enabled:
        raise ReproError(f"{mode} 실행에는 --enable이 필요합니다")
    if manifest["commands"]["run"] != "@common-signal":
        raise ReproError(f"공통 입력 runner 대상이 아닙니다: {manifest['id']}")
    profile_path_value, profile = load_profile(profile_name)
    if manifest["environments"].get(profile["backend"]) == "not-applicable":
        raise ReproError(f"{manifest['id']}은 {profile['backend']} 환경 실행 대상이 아닙니다")
    check_private_credentials(profile)
    binary, config = detector_paths(profile)
    root = run_root(profile)
    destination = root / run_id_value
    if destination.exists() or destination.is_symlink():
        raise ReproError(f"기존 run은 덮어쓰지 않습니다: {destination}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id_value}.", dir=root))
    try:
        observations = temporary / "observations.jsonl"
        generate = load_signal_generator()
        generator_meta = generate(manifest["signal_generator"], mode, run_id_value, observations)
        duration_s = (int(generator_meta["duration_ms"]) + 999) // 1000
        if duration_s > manifest["safety"]["max_duration_s"] or duration_s > profile["limits"]["max_duration_s"]:
            raise ReproError("생성된 입력이 manifest/profile 실행시간 상한을 넘었습니다")
        input_stats = validate_observations(observations)
        alerts, detector_meta = detector_alerts(binary, config, observations)
        write_jsonl(temporary / "detector.jsonl", alerts)
        target_rule = manifest["detection"]["expected_rule"]
        target_alerts = [row for row in alerts if row.get("action") == "RAISE" and row.get("rule") == target_rule]
        detector_ok = len(target_alerts) == 0 if mode == "control" else len(target_alerts) >= 1
        detection_latency_ms = None
        if target_alerts and generator_meta["attack_started_at_ms"] is not None:
            try:
                detection_latency_ms = int(target_alerts[0]["t"]) - int(generator_meta["attack_started_at_ms"])
            except (KeyError, TypeError, ValueError):
                detection_latency_ms = None
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        run = {
            "schema": "ran-reproducer.run.v1",
            "run_id": run_id_value,
            "scenario_id": manifest["id"],
            "rule_ids": manifest["rule_ids"],
            "mode": mode,
            "profile": profile["id"],
            "reproduction_level": manifest["reproduction_level"],
            "started_at": now,
            "period_ms": 100,
            "source": generator_meta,
            "detector": detector_meta,
            "integrity": {
                "manifest_sha256": sha256(manifest_path),
                "profile_sha256": sha256(profile_path_value),
                "controller_sha256": sha256(Path(__file__).resolve()),
            },
            "clock": {"source": "fixture", "offset_ms": 0, "within_tolerance": True},
            "claims": {
                "live_protocol_path_observed": False,
                "rf_cause_observed": False,
                "service_denial_observed": False,
            },
        }
        write_json(temporary / "run.json", run)
        oracle = [{
            "schema": "ran-reproducer.oracle.v1",
            "run_id": run_id_value,
            "scenario_id": manifest["id"],
            "mode": mode,
            "expected_rule": target_rule,
            "expected_raise": mode != "control",
            "source": "reproducer-control-plane",
        }]
        write_jsonl(temporary / "oracle.jsonl", oracle)
        dimensions = {
            "mechanism": "not_observed" if manifest["reproduction_level"] == "detector-input-emulation" else "inconclusive",
            "detection_input": "pass",
            "detector_result": "pass" if detector_ok else "fail",
            "service_impact": "not_observed",
        }
        if any(value not in STATUSES for value in dimensions.values()):
            raise ReproError("내부 verdict 상태가 잘못됐습니다")
        verdict = {
            "schema": "ran-reproducer.verdict.v1",
            "run_id": run_id_value,
            "passed": detector_ok,
            "expected_rule": target_rule,
            "observed_alerts": len(target_alerts),
            "detection_latency_ms": detection_latency_ms,
            "dimensions": dimensions,
        }
        write_json(temporary / "verdict.json", verdict)
        (temporary / "report.md").write_text(report_text(run, verdict, input_stats, detector_meta), encoding="utf-8")
        seal(temporary, run_id_value)
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    if not detector_ok:
        raise ReproError(f"예상 탐지 결과와 다릅니다: {destination}")
    return destination


def verify_run(path: Path) -> dict[str, Any]:
    directory(path, "run")
    expected_files = set(REQUIRED_FILES) | {"evidence_manifest.json"}
    actual_files = {item.name for item in path.iterdir()}
    if actual_files != expected_files or any(item.is_symlink() or not item.is_file() for item in path.iterdir()):
        raise ReproError("run 파일 집합이 공통 계약과 다릅니다")
    run = load_object(path / "run.json", "run")
    verdict = load_object(path / "verdict.json", "verdict")
    manifest = load_object(path / "evidence_manifest.json", "evidence manifest")
    if run.get("schema") != "ran-reproducer.run.v1" or verdict.get("schema") != "ran-reproducer.verdict.v1":
        raise ReproError("공통 run/verdict schema가 아닙니다")
    if run.get("run_id") != path.name or verdict.get("run_id") != path.name or manifest.get("run_id") != path.name:
        raise ReproError("run identity가 일치하지 않습니다")
    if manifest.get("schema") != "ran-reproducer.evidence.v1" or not isinstance(manifest.get("files"), dict):
        raise ReproError("evidence manifest schema가 잘못됐습니다")
    for name in REQUIRED_FILES:
        expected = manifest["files"].get(name)
        file_path = regular(path / name, name)
        if not isinstance(expected, dict) or expected.get("size") != file_path.stat().st_size or expected.get("sha256") != sha256(file_path):
            raise ReproError(f"증거 해시가 다릅니다: {name}")
    validate_observations(path / "observations.jsonl")
    return {"run_id": path.name, "passed": verdict.get("passed") is True, "files": len(REQUIRED_FILES)}


def resolve_run(name: str, profile_name: str | None = None) -> Path:
    if not RUN_ID.fullmatch(name):
        raise ReproError("안전한 RUN_ID가 필요합니다")
    profile = load_profile(profile_name)[1] if profile_name else None
    return run_root(profile) / name


def replay_run(path: Path, profile_name: str) -> dict[str, Any]:
    verify_run(path)
    _, profile = load_profile(profile_name)
    binary, config = detector_paths(profile)
    run = load_object(path / "run.json", "run")
    alerts, metadata = detector_alerts(binary, config, path / "observations.jsonl")
    expected_rule = run["rule_ids"][0]
    target = [row for row in alerts if row.get("action") == "RAISE" and row.get("rule") == expected_rule]
    expected = run["mode"] != "control"
    return {
        "run_id": run["run_id"],
        "expected_rule": expected_rule,
        "expected_raise": expected,
        "observed_raise_count": len(target),
        "passed": (len(target) == 0) if not expected else (len(target) >= 1),
        "detector": metadata,
    }


def campaign(scenario: str, campaign_id: str, profile_name: str, enabled: bool) -> Path:
    if not RUN_ID.fullmatch(campaign_id):
        raise ReproError("안전한 CAMPAIGN_ID가 필요합니다")
    if not enabled:
        raise ReproError("campaign에는 --enable이 필요합니다")
    _, manifest = resolve_manifest(scenario)
    children = []
    for index in range(1, 4):
        for mode in ("control", manifest["active_mode"]):
            child = f"{campaign_id}-{mode}-{index}"
            path = signal_run(scenario, mode, child, profile_name, mode != "control")
            verify_run(path)
            verdict = load_object(path / "verdict.json", "verdict")
            children.append({"run_id": child, "mode": mode, "set_index": index, "passed": verdict["passed"]})
    root = run_root(load_profile(profile_name)[1])
    output = root / f"{campaign_id}-campaign.json"
    write_json(output, {
        "schema": "ran-reproducer.campaign.v1",
        "campaign_id": campaign_id,
        "scenario_id": manifest["id"],
        "matched_repetitions": 3,
        "passed": all(child["passed"] for child in children),
        "children": children,
    })
    return output


def command_catalog(as_json: bool) -> None:
    values = [value for _, value in manifests()]
    if as_json:
        print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"{'ID':<32} {'룰':<12} {'유형':<30} 이름 (별칭)")
    labels = {
        "protocol": "프로토콜 재현",
        "protocol-result-emulation": "프로토콜 결과 에뮬레이션",
        "protocol-observation-emulation": "프로토콜 관측 에뮬레이션",
        "detector-input-emulation": "탐지 입력 에뮬레이션",
    }
    for value in values:
        aliases = ",".join(value.get("aliases", [])) or "-"
        print(f"{value['id']:<32} {','.join(value['rule_ids']):<12} {labels[value['reproduction_level']]:<30} {value['name']} ({aliases})")


def command_coverage(as_json: bool) -> None:
    coverage: dict[str, list[dict[str, Any]]] = {}
    for path, value in manifests():
        for rule in value["rule_ids"]:
            coverage.setdefault(rule, []).append({
                "scenario_id": value["id"],
                "module": value["module"],
                "manifest": str(path.relative_to(ROOT)),
                "p5": value["environments"]["p5"],
                "ota": value["environments"]["ota"],
                "reproduction_level": value["reproduction_level"],
            })
    if as_json:
        print(json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"{'룰':<12} {'p5':<15} {'OTA':<15} {'재현 수준':<30} 시나리오")
    for rule in sorted(coverage):
        for item in coverage[rule]:
            print(f"{rule:<12} {item['p5']:<15} {item['ota']:<15} {item['reproduction_level']:<30} {item['scenario_id']}")


def command_doctor(profile_name: str) -> None:
    head = check_qualified_checkout()
    manifest_count = len(manifests())
    profile_path_value, profile = load_profile(profile_name)
    check_private_credentials(profile)
    print(f"OK reproducer checkout: {head}")
    print(f"OK manifest: {manifest_count}개")
    print(f"OK profile: {profile_path_value}")
    if profile["backend"] == "p5":
        live = live_e2e_settings(profile)
        verified = p5_remote_components(profile)
        print(f"OK detector(CU): {profile['detector']['binary']} ({verified['detector_sha256']})")
        print(f"OK detector config(CU): {profile['detector']['config']} ({verified['detector_config_sha256']})")
        print(f"OK telemetry(CU): {profile['telemetry']['binary']} ({verified['telemetry_sha256']}) period_ms=100")
        print(f"OK live E2E: {live['CU_PLATFORM_ROOT']} env={live['CU_DASHBOARD_ENV']} node={live['CU_TELEMETRY_NODE']}")
    else:
        binary, config = detector_paths(profile)
        telemetry_binary = regular(Path(profile["telemetry"]["binary"]), "telemetry binary")
        if not os.access(telemetry_binary, os.X_OK):
            raise ReproError(f"telemetry binary가 실행 가능하지 않습니다: {telemetry_binary}")
        print(f"OK detector: {binary} ({sha256(binary)})")
        print(f"OK detector config: {config} ({sha256(config)})")
        print(f"OK telemetry: {telemetry_binary} period_ms=100")


def command_checkout() -> None:
    print(f"OK reproducer checkout: {check_qualified_checkout()}")


def command_env(profile_name: str) -> None:
    _, profile = load_profile(profile_name)
    for key, value in sorted(profile["environment"].items()):
        print(f"{key}={value}")
    print(f"RAN_REPRO_BACKEND={profile['backend']}")
    print(f"RAN_REPRO_PROFILE_ID={profile['id']}")
    print(f"RAN_REPRO_RUN_ROOT={profile['run_root']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("catalog", "coverage"):
        child = sub.add_parser(name)
        child.add_argument("--json", action="store_true")
    sub.add_parser("validate")
    sub.add_parser("checkout")
    seal_run = sub.add_parser("seal")
    seal_run.add_argument("run_dir")
    seal_run.add_argument("run_id")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--profile", required=True)
    env = sub.add_parser("env")
    env.add_argument("--profile", required=True)
    run = sub.add_parser("signal-run")
    run.add_argument("scenario")
    run.add_argument("mode")
    run.add_argument("run_id")
    run.add_argument("--profile", required=True)
    run.add_argument("--enable", action="store_true")
    campaigns = sub.add_parser("signal-campaign")
    campaigns.add_argument("scenario")
    campaigns.add_argument("campaign_id")
    campaigns.add_argument("--profile", required=True)
    campaigns.add_argument("--enable", action="store_true")
    for name in ("verify", "report"):
        child = sub.add_parser(name)
        child.add_argument("run_id")
        child.add_argument("--profile")
    replay = sub.add_parser("replay")
    replay.add_argument("run_id")
    replay.add_argument("--profile", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            command_catalog(args.json)
        elif args.command == "coverage":
            command_coverage(args.json)
        elif args.command == "validate":
            found = manifests()
            print(f"manifest-validation: ok ({len(found)} modules)")
        elif args.command == "checkout":
            command_checkout()
        elif args.command == "seal":
            command_seal(args.run_dir, args.run_id)
        elif args.command == "doctor":
            command_doctor(args.profile)
        elif args.command == "env":
            command_env(args.profile)
        elif args.command == "signal-run":
            print(signal_run(args.scenario, args.mode, args.run_id, args.profile, args.enable))
        elif args.command == "signal-campaign":
            print(campaign(args.scenario, args.campaign_id, args.profile, args.enable))
        elif args.command == "verify":
            print(json.dumps(verify_run(resolve_run(args.run_id, args.profile)), ensure_ascii=False, sort_keys=True))
        elif args.command == "report":
            path = resolve_run(args.run_id, args.profile)
            verify_run(path)
            print(regular(path / "report.md", "report").read_text(encoding="utf-8"), end="")
        elif args.command == "replay":
            result = replay_run(resolve_run(args.run_id, args.profile), args.profile)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result["passed"] else 1
    except (OSError, ReproError, subprocess.TimeoutExpired) as error:
        print(f"reproctl: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
