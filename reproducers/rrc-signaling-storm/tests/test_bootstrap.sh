#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
OAI="$TMP/oai"
git init -q "$OAI"
printf 'cmake_targets/\n' >"$OAI/.gitignore"
printf 'baseline\n' >"$OAI/README"
git -C "$OAI" add .
git -C "$OAI" -c user.name=test -c user.email=test@example.invalid commit -qm baseline
EXPECT_COMMIT=$(git -C "$OAI" rev-parse HEAD)
BUILD="$OAI/cmake_targets/ran_build/build"
mkdir -p "$BUILD"
printf 'stock\n' >"$BUILD/nr-uesoftmodem"
chmod +x "$BUILD/nr-uesoftmodem"
printf 'stock\n' >"$BUILD/liboai_zmqdevif.so"

output=$(OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap")
[[ $output == *'stock provenance is not verified'* ]]

cat >"$OAI/cmake_targets/build_oai" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$OAI/cmake_targets/build_oai"
output=$(OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap" --force)
[[ $output == *'stock provenance is not verified'* ]]

mkdir "$TMP/stubs"
cat >"$TMP/stubs/git" <<'EOF'
#!/bin/sh
if [ "$3" = status ]; then exit 97; fi
exec "$REAL_GIT" "$@"
EOF
chmod +x "$TMP/stubs/git"
if PATH="$TMP/stubs:$PATH" REAL_GIT="$(command -v git)" OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" \
   "$ROOT/bin/rss-bootstrap" >/dev/null 2>&1; then
  echo 'bootstrap ignored a git status failure' >&2
  exit 1
fi
[[ $(git -C "$OAI" rev-parse HEAD) == "$EXPECT_COMMIT" ]]

printf 'later commit\n' >>"$OAI/README"
git -C "$OAI" add README
git -C "$OAI" -c user.name=test -c user.email=test@example.invalid commit -qm later
later=$(git -C "$OAI" rev-parse HEAD)
if OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap" >/dev/null 2>&1; then
  echo 'bootstrap reused a build from a different source commit' >&2
  exit 1
fi
[[ $(git -C "$OAI" rev-parse HEAD) == "$later" ]]
git -C "$OAI" checkout -q --detach "$EXPECT_COMMIT"

printf 'modified\n' >>"$OAI/README"
if OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap" >/dev/null 2>&1; then
  echo 'bootstrap accepted a dirty tree at the expected commit' >&2
  exit 1
fi
git -C "$OAI" checkout -- README

printf 'RSS_SHARE_LOCKSTEP\n' >"$BUILD/nr-uesoftmodem"
if OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap" >/dev/null 2>&1; then
  echo 'bootstrap accepted an RSS UE artifact' >&2
  exit 1
fi
printf 'stock\n' >"$BUILD/nr-uesoftmodem"
printf 'RSS_ZMQ_TX_WAIT_US\n' >"$BUILD/liboai_zmqdevif.so"
if OAI="$OAI" EXPECT_COMMIT="$EXPECT_COMMIT" "$ROOT/bin/rss-bootstrap" >/dev/null 2>&1; then
  echo 'bootstrap accepted an RSS ZMQ artifact' >&2
  exit 1
fi
echo 'bootstrap guards: ok'
