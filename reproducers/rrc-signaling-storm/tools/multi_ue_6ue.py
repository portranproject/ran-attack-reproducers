#!/usr/bin/env python3
"""Six-endpoint extension of the official-derived five-UE ZMQ flowgraph."""

from gnuradio import blocks, gr, zeromq

from multi_ue_5ue import main, multi_ue_scenario


class multi_ue_6ue(multi_ue_scenario):
    def __init__(self):
        super().__init__()

        self.ue6_source = zeromq.req_source(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2601", self.zmq_timeout,
            False, self.zmq_hwm, False
        )
        self.ue6_sink = zeromq.rep_sink(
            gr.sizeof_gr_complex, 1, "tcp://127.0.0.1:2600", self.zmq_timeout,
            False, self.zmq_hwm, True
        )
        self.ue6_ul = blocks.multiply_const_cc(1.0)
        self.ue6_dl = blocks.multiply_const_cc(1.0)

        self.connect((self.ue6_source, 0), (self.ue6_ul, 0))
        self.connect((self.ue6_ul, 0), (self.blocks_add_xx_0, 5))
        self.connect((self.blocks_throttle_0, 0), (self.ue6_dl, 0))
        self.connect((self.ue6_dl, 0), (self.ue6_sink, 0))


if __name__ == "__main__":
    main(multi_ue_6ue)
