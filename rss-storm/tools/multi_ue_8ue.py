#!/usr/bin/env python3
"""Eight-endpoint extension of the official-derived seven-UE ZMQ flowgraph."""

from gnuradio import blocks, gr, zeromq

from multi_ue_7ue import main, multi_ue_7ue


class multi_ue_8ue(multi_ue_7ue):
    def __init__(self):
        super().__init__()

        self.ue8_source = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2801", self.zmq_timeout,
            False, self.zmq_hwm, False
        )
        self.ue8_sink = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2800", self.zmq_timeout,
            False, self.zmq_hwm, True
        )
        self.ue8_ul = blocks.multiply_const_cc(1.0)
        self.ue8_dl = blocks.multiply_const_cc(1.0)

        self.connect((self.ue8_source, 0), (self.ue8_ul, 0))
        self.connect((self.ue8_ul, 0), (self.blocks_add_xx_0, 7))
        self.connect((self.blocks_throttle_0, 0), (self.ue8_dl, 0))
        self.connect((self.ue8_dl, 0), (self.ue8_sink, 0))


if __name__ == "__main__":
    main(multi_ue_8ue)
