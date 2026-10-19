#!/usr/bin/env bash
# Apply the A-type reproducer patch to the DU box's OAI tree and rebuild the UE.
# Run ON THE DU BOX. Nothing here touches OCUDU (gNB).
set -euo pipefail

OAI=${OAI:-/root/OAI}
PATCH=${PATCH:-/root/rss-ue.patch}
BRANCH=${BRANCH:-rss-ue-a-type}
BUILD="$OAI/cmake_targets/ran_build/build"
BIN="$BUILD/nr-uesoftmodem"

echo "== tree state before"
git -C "$OAI" rev-parse HEAD
git -C "$OAI" describe --tags --always
git -C "$OAI" status --porcelain | head

# 1. keep a way back: original binary + a named branch for the patch
if [[ -f "$BIN" && ! -f "$BIN.orig" ]]; then
  cp -p "$BIN" "$BIN.orig"
  echo "saved $BIN.orig"
fi

if git -C "$OAI" rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  git -C "$OAI" checkout "$BRANCH"
else
  git -C "$OAI" checkout -b "$BRANCH"
fi

# 2. apply (refuse to go on if it does not apply cleanly)
git -C "$OAI" apply --check --verbose "$PATCH"
git -C "$OAI" apply "$PATCH"
git -C "$OAI" --no-pager diff --stat

# 3. rebuild only the UE target
cmake --build "$BUILD" --target nr-uesoftmodem -- -j"$(nproc)"
ls -la "$BIN" "$BIN.orig" 2>/dev/null || true
echo "== done. attack is OFF unless --rss.enable 1 is passed."
