#!/usr/bin/env python3
"""Headless broker that folds one attack slot and N normal UE RUs into one cell."""

import ipaddress
import os
import signal
import threading

from gnuradio import blocks, gr, zeromq


def endpoint_indices(spec):
    """1부터 세는 endpoint 번호 목록을 "1-10,12" 형태에서 읽는다."""
    values = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                first, last = (int(value) for value in part.split("-", 1))
                if last < first:
                    raise ValueError("endpoint 범위가 뒤집혔습니다")
                values.update(range(first, last + 1))
            else:
                values.add(int(part))
        except ValueError as exc:
            raise ValueError("endpoint 번호 목록이 잘못됐습니다") from exc
    if any(value < 1 for value in values):
        raise ValueError("endpoint 번호는 1 이상이어야 합니다")
    return frozenset(values)


def endpoint_hosts(spec):
    """슬롯 범위별 원격 호스트를 "1-45=172.31.1.12,46-90=172.31.1.13" 형태에서 읽는다."""
    hosts = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError("원격 슬롯 매핑은 슬롯=호스트 형식이어야 합니다")
        slot_spec, host = part.split("=", 1)
        _address(host.strip(), "NORMAL_UE_BROKER_REMOTE_HOSTS")
        for slot in endpoint_indices(slot_spec):
            if slot in hosts:
                raise ValueError("원격 슬롯이 중복됐습니다")
            hosts[slot] = host.strip()
    return hosts


def _address(value, label):
    try:
        ipaddress.IPv4Address(value)
    except ValueError as exc:
        raise ValueError(f"{label}는 IPv4 주소여야 합니다") from exc
    return value


class SameCellBroker(gr.top_block):
    def __init__(self, endpoint_count, attack_slots=0, persistent_attack=False,
                 bind_addr="127.0.0.1", remote_hosts=None):
        super().__init__("normal UE same-cell broker")
        self.timeout = 100
        self.hwm = -1
        du_dl = zeromq.req_source(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2000", self.timeout, False, self.hwm, False)
        du_ul = zeromq.rep_sink(gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2001", self.timeout, False, self.hwm, True)
        throttle = blocks.throttle(gr.sizeof_gr_complex, 23.04e6 / 4, True)
        self.uplink = blocks.add_vcc(1)
        self.ue_ul = []
        self.ue_dl = []
        self.slot_ul_selectors = []
        self.slot_dl_selectors = []
        self.slot_ul_gates = []
        self.slot_dl_gates = []
        self.slot_ul_retire_selectors = []
        self.slot_ul_zero_sources = []
        self.warm_slots = set()
        self.persistent_attack = persistent_attack
        self.attack_retired = False
        self.connect((du_dl, 0), (throttle, 0))
        self.connect((self.uplink, 0), (du_ul, 0))
        for index in range(endpoint_count):
            port = 2100 + 100 * index
            ue_host = (remote_hosts or {}).get(index + 1, "127.0.0.1")
            ul = zeromq.req_source(gr.sizeof_gr_complex, 1, f"tcp://{ue_host}:{port + 1}", self.timeout, False, self.hwm, False)
            dl = zeromq.rep_sink(gr.sizeof_gr_complex, 1, f"tcp://{bind_addr}:{port}", self.timeout, False, self.hwm, True)
            self.ue_ul.append(ul)
            self.ue_dl.append(dl)
            if index >= attack_slots:
                self.connect((ul, 0), (self.uplink, index))
                self.connect((throttle, 0), (dl, 0))
                continue
            if persistent_attack:
                ul_selector = blocks.selector(gr.sizeof_gr_complex, 0, 0)
                ul_zero = blocks.null_source(gr.sizeof_gr_complex)
                ul_gate = blocks.multiply_const_cc(0.0)
                # Keep the UE sample clock aligned while suppressing only its uplink.
                dl_gate = blocks.multiply_const_cc(1.0)
                self.slot_ul_retire_selectors.append(ul_selector)
                self.slot_ul_zero_sources.append(ul_zero)
                self.slot_ul_gates.append(ul_gate)
                self.slot_dl_gates.append(dl_gate)
                self.connect((ul, 0), (ul_selector, 0))
                self.connect((ul_zero, 0), (ul_selector, 1))
                self.connect((ul_selector, 0), (ul_gate, 0))
                self.connect((ul_gate, 0), (self.uplink, index))
                self.connect((throttle, 0), (dl_gate, 0))
                self.connect((dl_gate, 0), (dl, 0))
                continue
            attack_port = 2100 + 100 * (endpoint_count + index)
            attack_ul = zeromq.req_source(
                gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{attack_port + 1}",
                self.timeout, False, self.hwm, False
            )
            attack_dl = zeromq.rep_sink(
                gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{attack_port}",
                self.timeout, False, self.hwm, True
            )
            ul_selector = blocks.selector(gr.sizeof_gr_complex, 0, 0)
            dl_selector = blocks.selector(gr.sizeof_gr_complex, 0, 0)
            dl_discard = blocks.null_sink(gr.sizeof_gr_complex)
            self.slot_ul_selectors.append(ul_selector)
            self.slot_dl_selectors.append(dl_selector)
            self.connect((ul, 0), (ul_selector, 0))
            self.connect((attack_ul, 0), (ul_selector, 1))
            self.connect((ul_selector, 0), (self.uplink, index))
            self.connect((throttle, 0), (dl, 0))
            self.connect((throttle, 0), (dl_selector, 0))
            self.connect((dl_selector, 0), (dl_discard, 0))
            self.connect((dl_selector, 1), (attack_dl, 0))

    def select_attack_slots(self, mode, slots):
        if self.persistent_attack:
            if mode not in {"standby", "warmup", "attack", "retire"}:
                raise ValueError("persistent attack slots accept standby, warmup, attack, or retire")
            if self.attack_retired and mode != "retire":
                raise ValueError("retired attack slots cannot be re-enabled")
            if mode == "retire":
                for selector in self.slot_ul_retire_selectors:
                    selector.set_input_index(1)
                self.attack_retired = True
            for index, ul_gate in enumerate(self.slot_ul_gates, start=1):
                gain = 1.0 if mode == "attack" and index in slots else 0.0
                ul_gate.set_k(gain)
            return
        if mode == "warmup":
            for index, selector in enumerate(self.slot_dl_selectors, start=1):
                selector.set_output_index(1 if index in slots else 0)
            self.warm_slots = set(slots)
        elif mode == "attack":
            if not slots <= self.warm_slots:
                raise ValueError("attack slots must be warmed first")
            for index, selector in enumerate(self.slot_ul_selectors, start=1):
                selector.set_input_index(1 if index in slots else 0)
        elif mode == "placeholder":
            for selector in self.slot_ul_selectors:
                selector.set_input_index(0)
            for selector in self.slot_dl_selectors:
                selector.set_output_index(0)
            self.warm_slots.clear()
        else:
            raise ValueError("invalid selection mode")


def main():
    endpoint_count = int(os.environ.get("NORMAL_UE_BROKER_ENDPOINTS", "6"))
    attack_slots = int(os.environ.get("NORMAL_UE_BROKER_ATTACK_SLOTS", "0"))
    control_path = os.environ.get("NORMAL_UE_BROKER_CONTROL", "")
    persistent_attack = os.environ.get("NORMAL_UE_BROKER_PERSISTENT_ATTACK", "0") == "1"
    max_endpoints = int(os.environ.get("NORMAL_UE_BROKER_MAX_ENDPOINTS", "15"))
    bind_addr = os.environ.get("NORMAL_UE_BROKER_BIND_ADDR", "127.0.0.1")
    remote_spec = os.environ.get("NORMAL_UE_BROKER_REMOTE_HOSTS", "")
    if endpoint_count < 2 or endpoint_count > max_endpoints:
        raise SystemExit("NORMAL_UE_BROKER_ENDPOINTS must be 2..15")
    try:
        _address(bind_addr, "NORMAL_UE_BROKER_BIND_ADDR")
        remote_hosts = endpoint_hosts(remote_spec) if remote_spec else {}
        if remote_hosts:
            if not persistent_attack:
                raise ValueError("원격 UE는 persistent attack slot에서만 지원합니다")
            if max(remote_hosts) > endpoint_count:
                raise ValueError("원격 endpoint 번호가 전체 endpoint 수를 넘습니다")
    except ValueError as exc:
        raise SystemExit(f"broker 원격 설정 오류: {exc}")
    if attack_slots < 0 or attack_slots >= endpoint_count:
        raise SystemExit("NORMAL_UE_BROKER_ATTACK_SLOTS must be 0..endpoint_count-1")
    if persistent_attack and attack_slots == 0:
        raise SystemExit("persistent attack mode requires at least one attack slot")
    if attack_slots and (not control_path.startswith("/") or os.path.islink(control_path)):
        raise SystemExit("NORMAL_UE_BROKER_CONTROL must be an absolute non-symlink path")
    stopped = threading.Event()
    reset_attack = threading.Event()
    flowgraph = SameCellBroker(endpoint_count, attack_slots, persistent_attack,
                               bind_addr, remote_hosts)

    def stop(_signum=None, _frame=None):
        stopped.set()

    def request_attack_reset(_signum=None, _frame=None):
        reset_attack.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGUSR1, request_attack_reset)
    flowgraph.start()
    while not stopped.wait(0.1):
        if reset_attack.is_set():
            reset_attack.clear()
            try:
                raw = open(control_path, encoding="utf-8").read().strip()
                if raw in {"placeholder", "standby", "retire"}:
                    slots = set()
                    mode = raw
                elif raw.startswith("warmup ") or raw.startswith("attack "):
                    mode, values = raw.split(" ", 1)
                    slots = {int(value) for value in values.split(",")}
                    if not slots or min(slots) < 1 or max(slots) > attack_slots:
                        raise ValueError("attack slot is out of range")
                else:
                    raise ValueError("invalid broker control")
                flowgraph.select_attack_slots(mode, slots)
                print(
                    f"SAME_CELL_SLOT_SELECTION mode={mode} slots={','.join(map(str, sorted(slots)))}",
                    flush=True,
                )
            except Exception as exc:
                print(f"SAME_CELL_SLOT_SELECTION_FAILED {exc}", flush=True)
    flowgraph.stop()
    flowgraph.wait()


if __name__ == "__main__":
    main()
