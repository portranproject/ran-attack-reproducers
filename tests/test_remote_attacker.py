import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / "workloads/normal-ue/tools/same_cell_broker.py"
SAME_CELL = ROOT / "workloads/normal-ue/bin/same-cell-run"
AUTH_RUNNER = ROOT / "reproducers/authentication-timeout-exhaustion/bin/auth-stall-cell-run"
MULTI_RU = ROOT / "reproducers/authentication-timeout-exhaustion/analysis/multi_ru_config.py"
CHANGED = (BROKER, SAME_CELL, AUTH_RUNNER, MULTI_RU)


def _source(path: Path, count: int) -> None:
    blocks = "".join(
        f'uicc{i} = {{ imsi="{i}"; key="00"; opc="00"; }}\n' for i in range(count)
    )
    path.write_text(blocks, encoding="utf-8")


def _broker_helpers():
    tree = ast.parse(BROKER.read_text(encoding="utf-8"))
    keep = [
        node
        for node in tree.body
        if isinstance(node, ast.Import) and any(alias.name == "ipaddress" for alias in node.names)
    ]
    keep += [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in {"endpoint_indices", "_address"}
    ]
    namespace = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(BROKER), "exec"), namespace)
    return namespace


class RemoteBrokerEndpointTest(unittest.TestCase):
    def test_endpoint_list_parsing(self):
        helpers = _broker_helpers()
        assert helpers["endpoint_indices"]("1-3,5") == frozenset({1, 2, 3, 5})
        assert helpers["endpoint_indices"]("7") == frozenset({7})
        for bad in ("0", "x", "1-", "2-1"):
            with self.assertRaises(ValueError):
                helpers["endpoint_indices"](bad)
        assert helpers["_address"]("172.31.1.12", "X") == "172.31.1.12"
        for bad in ("172.31.1.300", "host", "127.0.0.1:1"):
            with self.assertRaises(ValueError):
                helpers["_address"](bad, "X")

    def test_remote_host_only_for_listed_endpoints(self):
        text = BROKER.read_text(encoding="utf-8")
        assert 'ue_host = remote_host if index + 1 in remote_ues else "127.0.0.1"' in text
        assert 'os.environ.get("NORMAL_UE_BROKER_BIND_ADDR", "127.0.0.1")' in text
        assert 'os.environ.get("NORMAL_UE_BROKER_REMOTE_UES", "")' in text


class MultiRuHostTest(unittest.TestCase):
    def test_default_stays_loopback(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.conf"
            _source(src, 5)
            env = {**os.environ}
            env.pop("AUTH_STALL_CELL_ZMQ_TX_HOST", None)
            env.pop("AUTH_STALL_CELL_ZMQ_RX_HOST", None)
            done = subprocess.run(
                [sys.executable, str(MULTI_RU), str(src), str(Path(tmp) / "a.conf"), "5"],
                capture_output=True, text=True, env=env,
            )
            assert done.returncode == 0, done.stderr
            text = (Path(tmp) / "a.conf").read_text()
            assert "tcp://127.0.0.1:2101" in text
            assert "tcp://127.0.0.1:2100" in text

    def test_remote_hosts_are_used_and_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.conf"
            _source(src, 5)
            env = {**os.environ, "AUTH_STALL_CELL_ZMQ_TX_HOST": "172.31.1.12",
                   "AUTH_STALL_CELL_ZMQ_RX_HOST": "172.31.1.11"}
            done = subprocess.run(
                [sys.executable, str(MULTI_RU), str(src), str(Path(tmp) / "b.conf"), "5"],
                capture_output=True, text=True, env=env,
            )
            assert done.returncode == 0, done.stderr
            text = (Path(tmp) / "b.conf").read_text()
            assert "tcp://172.31.1.12:2101" in text
            assert "tcp://172.31.1.11:2100" in text
            assert "tcp://127.0.0.1:" not in text
            bad = {**env, "AUTH_STALL_CELL_ZMQ_TX_HOST": "attacker"}
            done = subprocess.run(
                [sys.executable, str(MULTI_RU), str(src), str(Path(tmp) / "c.conf"), "5"],
                capture_output=True, text=True, env=bad,
            )
            assert done.returncode != 0


class RemoteRunnerGateTest(unittest.TestCase):
    def test_remote_requires_three_settings(self):
        text = SAME_CELL.read_text(encoding="utf-8")
        for name in ("SAME_CELL_ATTACK_SSH", "SAME_CELL_REMOTE_UE_IP", "SAME_CELL_REMOTE_BROKER_IP"):
            assert f'{name}:-' in text
        assert "원격 공격 UE는 auth-timeout 진단에만 지원합니다" in text
        runner = AUTH_RUNNER.read_text(encoding="utf-8")
        assert "SAME_CELL_REMOTE_ATTACK" in runner
        assert "AUTH_STALL_CELL_ZMQ_TX_HOST" in runner
        assert "원격 same-cell endpoint 순서" in runner


class NoSensitiveLiteralsTest(unittest.TestCase):
    def test_no_imsi_shaped_or_amf_literal(self):
        imsi = re.compile(r"(?<![0-9])[0-9]{15}(?![0-9])")
        amf = re.compile(r"(?i)\bamf\s*=\s*\"?[0-9a-f]{4}")
        for path in CHANGED:
            text = path.read_text(encoding="utf-8")
            assert not imsi.search(text), f"IMSI 모양 15자리 숫자가 있습니다: {path}"
            assert not amf.search(text), f"AMF 값이 있습니다: {path}"


if __name__ == "__main__":
    unittest.main()
