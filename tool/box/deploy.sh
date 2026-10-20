#!/usr/bin/env bash
# Apply the A-type reproducer patch to the DU box's OAI tree and rebuild the UE.
# Run ON THE DU BOX. Nothing here touches OCUDU (gNB).
set -euo pipefail

OAI=${OAI:-/root/OAI}
PATCH=${PATCH:-/root/rss-ue.patch}
BRANCH=${BRANCH:-rss-ue-a-type}
BUILD="$OAI/cmake_targets/ran_build/build"
BIN="$BUILD/nr-uesoftmodem"
# zmq_radio.cpp builds into a separate shared library that the UE loads at
# runtime (--device.name oai_zmqdevif), so it needs its own build target.
DEVLIB="$BUILD/liboai_zmqdevif.so"

echo "== tree state before"
git -C "$OAI" rev-parse HEAD
git -C "$OAI" describe --tags --always
git -C "$OAI" status --porcelain | head

# 1. keep a way back: original binary + a named branch for the patch
if [[ -f "$BIN" && ! -f "$BIN.orig" ]]; then
  cp -p "$BIN" "$BIN.orig"
  echo "saved $BIN.orig"
fi
if [[ -f "$DEVLIB" && ! -f "$DEVLIB.orig" ]]; then
  cp -p "$DEVLIB" "$DEVLIB.orig"
  echo "saved $DEVLIB.orig"
fi

if git -C "$OAI" rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  git -C "$OAI" checkout "$BRANCH"
else
  git -C "$OAI" checkout -b "$BRANCH"
fi

# 2. apply (refuse to go on if it does not apply cleanly).
#    Re-deployable: drop any previous version of our edits first, so the same
#    script can roll a new patch revision onto a box that already has one.
#    Reset the whole tree, not just the RRC directory: the patch also touches
#    executables/ for RU sharing, and a narrow reset silently left the old
#    version in place (observed 2026-10-20, "patch does not apply").
git -C "$OAI" checkout -- .
git -C "$OAI" apply --check --verbose "$PATCH"
git -C "$OAI" apply "$PATCH"
git -C "$OAI" --no-pager diff --stat

# 3. rebuild the UE target *and* the ZMQ radio device.
#    Building only nr-uesoftmodem leaves the old liboai_zmqdevif.so in place,
#    so edits to radio/zmq/ apply to the source tree but never reach the run
#    (observed 2026-10-20: the tree had the TX-poll fix, the loaded device did
#    not, and `strings nr-uesoftmodem` could not see it either because the
#    device is a separate .so).
for t in nr-uesoftmodem oai_zmqdevif zmq_radio_static; do
  echo "== building $t"
  cmake --build "$BUILD" --target "$t" -- -j"$(nproc)"
done
ls -la "$BIN" "$BIN.orig" "$DEVLIB" "$DEVLIB.orig" 2>/dev/null || true

# 4. the knobs must be visible in the artifact that actually carries them:
#    RRC knobs in the executable, ZMQ knobs in the device library.
echo "== knob check"
printf "  nr-uesoftmodem  target_occupancy: %s\n" "$(strings "$BIN" | grep -c target_occupancy || true)"
printf "  liboai_zmqdevif RSS_ZMQ_TX_WAIT_US: %s\n" "$(strings "$DEVLIB" | grep -c RSS_ZMQ_TX_WAIT_US || true)"
echo "== done. attack is OFF unless --rss.enable 1 is passed."
