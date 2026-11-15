#!/usr/bin/env python3
"""Headless broker that folds one attack slot and N normal UE RUs into one cell."""

import os
import signal
import threading

from gnuradio import blocks, gr, zeromq


class SameCellBroker(gr.top_block):
    def __init__(self, endpoint_count, attack_slots=0, persistent_attack=False):
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
        self.warm_slots = set()
        self.persistent_attack = persistent_attack
        self.connect((du_dl, 0), (throttle, 0))
        self.connect((self.uplink, 0), (du_ul, 0))
        for index in range(endpoint_count):
            port = 2100 + 100 * index
            ul = zeromq.req_source(gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{port + 1}", self.timeout, False, self.hwm, False)
            dl = zeromq.rep_sink(gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{port}", self.timeout, False, self.hwm, True)
            self.ue_ul.append(ul)
            self.ue_dl.append(dl)
            if index >= attack_slots:
                self.connect((ul, 0), (self.uplink, index))
                self.connect((throttle, 0), (dl, 0))
                continue
            if persistent_attack:
                ul_gate = blocks.multiply_const_cc(0.0)
                dl_gate = blocks.multiply_const_cc(0.0)
                self.slot_ul_gates.append(ul_gate)
                self.slot_dl_gates.append(dl_gate)
                self.connect((ul, 0), (ul_gate, 0))
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
            if mode not in {"standby", "attack"}:
                raise ValueError("persistent attack slots accept standby or attack")
            for index, (ul_gate, dl_gate) in enumerate(
                zip(self.slot_ul_gates, self.slot_dl_gates), start=1
            ):
                gain = 1.0 if mode == "attack" and index in slots else 0.0
                ul_gate.set_k(gain)
                dl_gate.set_k(gain)
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
    if endpoint_count < 2 or endpoint_count > 11:
        raise SystemExit("NORMAL_UE_BROKER_ENDPOINTS must be 2..11")
    if attack_slots < 0 or attack_slots >= endpoint_count:
        raise SystemExit("NORMAL_UE_BROKER_ATTACK_SLOTS must be 0..endpoint_count-1")
    if persistent_attack and attack_slots == 0:
        raise SystemExit("persistent attack mode requires at least one attack slot")
    if attack_slots and (not control_path.startswith("/") or os.path.islink(control_path)):
        raise SystemExit("NORMAL_UE_BROKER_CONTROL must be an absolute non-symlink path")
    stopped = threading.Event()
    reset_attack = threading.Event()
    flowgraph = SameCellBroker(endpoint_count, attack_slots, persistent_attack)

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
                if raw in {"placeholder", "standby"}:
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
