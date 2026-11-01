#!/usr/bin/env python3
"""Headless two-endpoint ZMQ flowgraph: one load process and one witness."""

import signal
import threading

from gnuradio import blocks, gr, zeromq


class multi_ue_2ue(gr.top_block):
    def __init__(self):
        super().__init__("rss two-UE broker")
        self.timeout = timeout = 100
        self.hwm = hwm = -1

        du_dl = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2000", timeout, False, hwm, False
        )
        du_ul = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2001", timeout, False, hwm, True
        )
        ue1_ul = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2101", timeout, False, hwm, False
        )
        ue1_dl = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2100", timeout, False, hwm, True
        )
        ue2_ul = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2201", timeout, False, hwm, False
        )
        ue2_dl = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2200", timeout, False, hwm, True
        )
        uplink = blocks.add_vcc(1)
        self.witness_ul = ue2_ul
        self.uplink = uplink
        throttle = blocks.throttle(gr.sizeof_gr_complex, 23.04e6, True)

        self.connect((du_dl, 0), (throttle, 0))
        self.connect((throttle, 0), (ue1_dl, 0))
        self.connect((throttle, 0), (ue2_dl, 0))
        self.connect((ue1_ul, 0), (uplink, 0))
        self.connect((ue2_ul, 0), (uplink, 1))
        self.connect((uplink, 0), (du_ul, 0))

    def reset_witness_uplink(self):
        # req_source retains an outstanding request when its REP peer is replaced.
        self.lock()
        try:
            old = self.witness_ul
            self.disconnect((old, 0), (self.uplink, 1))
            self.witness_ul = None
            del old
            self.witness_ul = zeromq.req_source(
                gr.sizeof_gr_complex,
                1,
                "tcp://127.0.0.1:2201",
                self.timeout,
                False,
                self.hwm,
                False,
            )
            self.connect((self.witness_ul, 0), (self.uplink, 1))
        finally:
            self.unlock()
        print("RSS_BROKER_WITNESS_UPLINK_RESET port=2201", flush=True)


def main():
    stopped = threading.Event()
    reset_witness = threading.Event()
    flowgraph = multi_ue_2ue()

    def stop(_signum=None, _frame=None):
        stopped.set()

    def request_witness_reset(_signum=None, _frame=None):
        reset_witness.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGUSR1, request_witness_reset)
    flowgraph.start()
    while not stopped.wait(0.1):
        if reset_witness.is_set():
            reset_witness.clear()
            try:
                flowgraph.reset_witness_uplink()
            except Exception as exc:
                print(f"RSS_BROKER_WITNESS_UPLINK_RESET_FAILED {exc}", flush=True)
    flowgraph.stop()
    flowgraph.wait()


if __name__ == "__main__":
    main()
