# NOTICE

## What this is

A research tool that reproduces an RRC signaling storm (incomplete initial
access) against a 5G NR base station **you own**, for the purpose of testing
intrusion detection and mitigation.

## Intended use and limits

- Isolated testbeds only: RF-shielded enclosure, or a virtual radio such as ZMQ,
  on equipment you own or are explicitly authorised to test.
- Never against a public network, a shared cell, or any base station you do not
  own. Doing so is illegal in most jurisdictions.
- The attack is off by default. It only runs when `-e 1` is passed explicitly.
- Two independent kill switches are always armed when `MAX_DURATION_S > 0`:
  the in-process timer and an outer `timeout`.

## Attribution

This tool is a patch against OpenAirInterface's NR UE. It does not modify any
base station source.

- **OpenAirInterface (OAI)** — the UE this patch applies to.
  Patch baseline: commit `1c2f4d3c2e68181cdef9f426d161163147ad4b77` (tag
  `2026.w38`). That release identifies its source licence as the Common Source
  Software License 1.0 (`LicenseRef-CSSL-1.0`); consult OAI's `LICENSE` file for
  the controlling terms.
  https://gitlab.eurecom.fr/oai/openairinterface5g
- **radio/zmq in OAI** carries `SPDX-License-Identifier: BSD-3-Clause-Open-MPI`
  and is itself derived from the OCUDU/srsRAN ZMQ radio. The fixes in
  `radio/zmq/` in this patch are changes to that code.
- **OCUDU** (srsRAN-derived) was the base station under test. It is not modified
  and not redistributed here.
- The RRCSetupComplete-omission scenario (receive Msg4, skip `RRCSetupComplete`) follows the
  experimental setup described in the KAUST RRC storm validation paper
  (arXiv:2608.16441). Cite it if you publish results.
- `5gattacks/5g-rrc-storm` is the closest prior public implementation. It
  targets an older OAI commit and also changes gNB timers, which this tool does
  not. **It carries no licence file**, so no code from it is copied here.

Because the patch applies to OAI sources, redistribution of the *patched result*
must respect OAI's CSSL 1.0 terms. The patch, scripts and documentation in this
directory are the original work of this project; this repository does not add a
licence grant for third-party OAI code.
