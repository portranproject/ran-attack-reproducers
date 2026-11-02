"""Offline broker wiring checks; GNU Radio is replaced with small fakes."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TopBlock:
    def __init__(self, _name):
        self.connections = []
        self.disconnections = []

    def connect(self, source, sink):
        self.connections.append((source, sink))

    def disconnect(self, source, sink):
        self.disconnections.append((source, sink))

    def lock(self):
        pass

    def unlock(self):
        pass


class Zmq:
    serial = 0

    @classmethod
    def req_source(cls, *_args):
        cls.serial += 1
        return ("req", _args[2], cls.serial)

    @staticmethod
    def rep_sink(*args):
        return ("rep", args[2])


class Blocks:
    @staticmethod
    def throttle(*_args):
        return "throttle"

    @staticmethod
    def add_vcc(*_args):
        return "uplink"

class BrokerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake = types.ModuleType("gnuradio")
        fake.blocks = Blocks
        fake.gr = types.SimpleNamespace(top_block=TopBlock, sizeof_gr_complex=8)
        fake.zeromq = Zmq
        previous = sys.modules.get("gnuradio")
        sys.modules["gnuradio"] = fake
        try:
            spec = importlib.util.spec_from_file_location(
                "blind_zmq_broker", ROOT / "tools" / "zmq_broker.py"
            )
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)
        finally:
            if previous is None:
                del sys.modules["gnuradio"]
            else:
                sys.modules["gnuradio"] = previous

    def test_two_ue_wiring_is_fixed_for_the_whole_phase(self):
        broker = self.module.BlindBroker(2)
        self.assertEqual(len(broker.ue_uplinks), 2)
        self.assertEqual(broker.ue_uplinks[1][1], "tcp://127.0.0.1:2201")
        self.assertEqual(broker.ue_downlinks[1][1], "tcp://127.0.0.1:2200")

    def test_three_ue_wiring_adds_control_endpoint(self):
        broker = self.module.BlindBroker(3)
        self.assertEqual(broker.ue_uplinks[2][1], "tcp://127.0.0.1:2301")
        self.assertEqual(broker.ue_downlinks[2][1], "tcp://127.0.0.1:2300")


if __name__ == "__main__":
    unittest.main()
