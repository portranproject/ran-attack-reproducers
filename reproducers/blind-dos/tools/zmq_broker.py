#!/usr/bin/env python3
"""Headless ZMQ broker for two or three independent Blind DoS UE processes."""

import argparse
import signal
import threading

from gnuradio import blocks, gr, zeromq


class BlindBroker(gr.top_block):
    def __init__(self, ue_count: int):
        super().__init__("blind-dos UE broker")
        self.timeout = timeout = 100
        self.high_water_mark = high_water_mark = -1
        self.ue_count = ue_count

        du_downlink = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2000", timeout, False,
            high_water_mark, False,
        )
        du_uplink = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2001", timeout, False,
            high_water_mark, True,
        )
        self.throttle = throttle = blocks.throttle(gr.sizeof_gr_complex, 23.04e6, True)
        self.uplink = uplink = blocks.add_vcc(1)
        self.ue_uplinks = []
        self.ue_downlinks = []

        self.connect((du_downlink, 0), (throttle, 0))
        for index in range(ue_count):
            base = 2000 + (index + 1) * 100
            ue_uplink = zeromq.req_source(
                gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{base + 1}",
                timeout, False, high_water_mark, False,
            )
            ue_downlink = zeromq.rep_sink(
                gr.sizeof_gr_complex, 1, f"tcp://127.0.0.1:{base}",
                timeout, False, high_water_mark, True,
            )
            self.ue_uplinks.append(ue_uplink)
            self.ue_downlinks.append(ue_downlink)
            self.connect((throttle, 0), (ue_downlink, 0))
            self.connect((ue_uplink, 0), (uplink, index))
        self.connect((uplink, 0), (du_uplink, 0))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ues", type=int, choices=(2, 3), default=2)
    args = parser.parse_args()

    stopped = threading.Event()
    broker = BlindBroker(args.ues)

    def stop(_signum=None, _frame=None):
        stopped.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    broker.start()
    stopped.wait()
    broker.stop()
    broker.wait()


if __name__ == "__main__":
    main()
