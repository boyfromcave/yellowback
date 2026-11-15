#!/usr/bin/env bash
# Copyright (c) 2026 The Ycash developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://www.opensource.org/licenses/mit-license.php .

# The steps of the release-candidate qualification (testnet plan §5.3; qualify/README.md and the
# workspace's .github/workflows/rc-qualify.yml).
#
# In plain words: a release candidate is qualified by running the downloaded release files, not a
# fresh build, together with every other Yellowback program at the commits its release train names
# (releases/v<version>.yaml, beside this directory). Each command below is one of those runs; the
# workflow calls them one per job, and a developer can run any of them on a laptop the same way.
#
# This harness lived in ycash6 (qa/yellowback-rc-qualify.sh) until beta3 (process requirement P-1).
# It is the workspace's now: a fix here never moves a node's commit, and a run records this
# repository's commit (harness_commit) beside the node commits it qualified.
#
# Usage: qualify/rc-qualify.sh COMMAND [ARGS]
#   train FILE            read the release train FILE (scripts/release-train.py pins) and print its
#                         TRAIN_* lines, checked as `pins` does; a skeleton train (any `placeholder`
#                         value) is refused
#   install PKGDIR TREE   check the linux_x86_64 package in PKGDIR against PKGDIR/SHA256SUMS and put
#                         its ycashd, ycash-cli and ycash-tx into TREE/src (the version banner must be
#                         the package's)
#   pins FILE             print FILE's TRAIN_* lines (scripts/release-train.py pins) after checking
#                         every line's shape; the workflow appends them to $GITHUB_ENV
#   sidecars DEST         step 1's sidecars: yolo (--features regtest) and chain-viz at their train
#                         pins, the binaries copied to DEST (yellowback_stratum, yellowback_chainviz)
#   node-shard SUITE N OF step 1 against the package: shard N of OF of the node's own functional
#                         list SUITE (yellowback | stock), read from WS/ycash6's yellowback-tests.yml
#                         (qualify/rc-suites.py), run by its own rpc-tests.py on the release binaries
#                         in WS/ycash6/src; YOLO_BIN / CHAINVIZ_BIN name the sidecars
#   walk | yew | x402 | hawkeye | yecwallet
#                         step 2, the ecosystem walk: one client (or, for walk, the devnet's own
#                         clients: chain-viz, lightwalletd fork and baseline, yolo) at its train pin
#                         against the release binary
#   cross-line DD_TREE    step 3: the devnet with two ycash-dd nodes (DD_TREE/src/ycashd, built at
#                         the train's vault-params commit); the block hash, the vault state hash and
#                         the YED state hash agree at every 100th height (qualify/rc-crossline.py)
#   ceremony              step 4: the testnet launch ceremony rehearsed on regtest with each yb
#                         profile's maturity (contrib/testnet/ceremony, testnet plan §2.2, N2)
#
# Environment for the steps: WS (a scratch directory: WS/ycash6 is the ycash6 tree at the train's
# commit, with the release binaries in src/ (install); the clients are cloned beside it; the node's
# own tools (the devnet, the attest agent, the ceremony, the test framework) are read from WS/ycash6),
# RC_OUT (where each step writes its evidence, default $WS/rc-out), the TRAIN_* pins, and the
# toolchains each step names (cargo, go, node/npm, foundry, Qt) on PATH. Nothing here builds ycashd.
set -euo pipefail

die() { echo "rc-qualify: $*" >&2; exit 1; }
here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workspace=$(dirname -- "$here")

# Public repositories of the release train (repos.yaml urls; lightwalletd-dd's repository is "lightwalletd").
repo_url() {
  case "$1" in
    lightwalletd-dd) echo "https://github.com/boyfromcave/lightwalletd.git" ;;
    ycash-dd|yolo|chain-viz|yew|x402-ycash|hawkeye|yecwallet-dd) echo "https://github.com/boyfromcave/$1.git" ;;
    *) die "no repository for $1" ;;
  esac
}

pin() {  # the train's commit of a component (TRAIN_<NAME>_COMMIT), checked
  local var value
  var="TRAIN_$(printf '%s' "$1" | tr 'a-z-' 'A-Z_')_COMMIT"
  value=${!var:-}
  [[ $value =~ ^[0-9a-f]{40}$ ]] || die "$var is not set to a 40-hex commit (load the release train: pins)"
  printf '%s\n' "$value"
}

clone_at() {  # NAME DEST: the component at its train commit (every branch's history, blobs on demand)
  local name=$1 dest=$2 commit
  commit=$(pin "$name")
  [ -d "$dest/.git" ] || git clone -q --filter=blob:none "$(repo_url "$name")" "$dest"
  git -C "$dest" checkout -q --detach "$commit"
  [ "$(git -C "$dest" rev-parse HEAD)" = "$commit" ] || die "$name: checkout is not $commit"
  echo "$name at $commit"
}

need_ws() {
  : "${WS:?WS must name the scratch directory (WS/ycash6 = the ycash6 tree at the train commit)}"
  [ -x "$WS/ycash6/src/ycashd" ] || die "no release ycashd at $WS/ycash6/src/ycashd (run install first)"
  RC_OUT=${RC_OUT:-$WS/rc-out}
  mkdir -p "$RC_OUT"
  # The devnet tools find the workspace as the directory above the node tree; YEW's scripts look for repos.yaml.
  touch "$WS/repos.yaml"
  DEVNET="$WS/ycash6/contrib/yellowback/devnet/yellowback-devnet"
  # An absolute path: client scripts test it with [[ -x ]], which a bare command name fails.
  PY=$(command -v "${PYTHON:-python3}") || die "no python at ${PYTHON:-python3} (set PYTHON)"
}

attest_agent() {
  local target=${RUNNER_TEMP:-$WS}/attest-target
  (cd "$WS/ycash6/contrib/yellowback/attest" && CARGO_TARGET_DIR="$target" cargo build -q --release --locked)
  export YELLOWBACK_ATTEST_BIN="$target/release/yellowback-attest"
}

# Each client is built into its own target/ (CARGO_TARGET_DIR set, as the *_BIN paths below assume): a
# developer's cargo config or environment may name a shared target directory, which would leave them empty.
build_yolo() {  # the stratum pool at the train pin (YOLO_BIN): the walk and x402's stratum tests run it
  clone_at yolo "$WS/yolo"
  (cd "$WS/yolo" && CARGO_TARGET_DIR="$WS/yolo/target" cargo build -q --release --locked --features regtest)
  export YOLO_BIN="$WS/yolo/target/release/yolo"
}

lightwalletd() {  # the fork at the train pin (YELLOWBACK_LWD_BIN) and the baseline (lightwalletd-legacy)
  clone_at lightwalletd-dd "$WS/lightwalletd-dd"
  git -C "$WS/lightwalletd-dd" fetch -q origin "+refs/heads/lightwalletd-legacy:refs/heads/lightwalletd-legacy"
  mkdir -p "$WS/wt/lightwalletd-dd-bin"
  (cd "$WS/lightwalletd-dd" && CGO_ENABLED=0 go build -mod=vendor -o "$WS/wt/lightwalletd-dd-bin/lightwalletd" .)
  "$WS/lightwalletd-dd/scripts/build-baseline.sh" "$WS/wt/lightwalletd-legacy-bin"
  export YELLOWBACK_LWD_REPO="$WS/lightwalletd-dd" YELLOWBACK_LWD_BIN="$WS/wt/lightwalletd-dd-bin/lightwalletd"
}

cmd_install() {
  [ $# -eq 2 ] || die "usage: install PKGDIR TREE"
  local dir=$1 tree=$2 pkgs name ver tmp b banner
  pkgs=$(cd "$dir" && ls ycashd_v*_linux_x86_64.tar.gz 2>/dev/null || true)
  [ "$(printf '%s\n' "$pkgs" | grep -c .)" = 1 ] || die "expected exactly one ycashd_v*_linux_x86_64.tar.gz in $dir, found: ${pkgs:-none}"
  name=$pkgs
  ver=${name#ycashd_v}; ver=${ver%_linux_x86_64.tar.gz}
  [[ $ver =~ ^6\.2[12]\.[0-9]+(-(rc|beta)[1-9][0-9]*|-[1-9][0-9]*)?$ ]] || die "$name does not name a release version"
  [ -f "$dir/SHA256SUMS" ] || die "no SHA256SUMS in $dir"
  grep -qE "^[0-9a-f]{64}  $name\$" "$dir/SHA256SUMS" || die "SHA256SUMS does not list $name"
  (cd "$dir" && grep -E "^[0-9a-f]{64}  $name\$" SHA256SUMS | sha256sum -c -) || die "$name does not match SHA256SUMS"
  tmp=$(mktemp -d)
  tar -xzf "$dir/$name" -C "$tmp"
  mkdir -p "$tree/src"
  for b in ycashd ycash-cli ycash-tx; do
    [ -f "$tmp/ycashd_v${ver}_linux_x86_64/$b" ] || die "$name has no $b"
    rm -f "$tree/src/$b"
    install -m 0755 "$tmp/ycashd_v${ver}_linux_x86_64/$b" "$tree/src/$b"
  done
  rm -rf "$tmp"
  banner=$("$tree/src/ycashd" --version | head -1)
  case "$banner" in *"v$ver"*) ;; *) die "src/ycashd says '$banner', not v$ver" ;; esac
  echo "installed $name into $tree/src: $banner"
}

cmd_pins() {
  [ $# -eq 1 ] || die "usage: pins FILE"
  local line n=0
  while IFS= read -r line || [ -n "$line" ]; do
    [[ $line =~ ^TRAIN_[A-Z0-9_]+=[A-Za-z0-9./_-]+$ ]] || die "not a TRAIN_* pin line: $line"
    printf '%s\n' "$line"
    n=$((n + 1))
  done < "$1"
  [ "$n" -gt 0 ] || die "$1 holds no pins"
}

cmd_train() {
  [ $# -eq 1 ] || die "usage: train FILE"
  local raw rc=0
  raw=$(python3 "$workspace/scripts/release-train.py" pins "$1") || rc=$?
  [ "$rc" -eq 0 ] || die "the release train $1 cannot be qualified (above)"
  cmd_pins /dev/stdin <<<"$raw"
}

cmd_sidecars() {
  [ $# -eq 1 ] || die "usage: sidecars DEST"
  : "${WS:?WS must name the scratch directory}"
  mkdir -p "$1"
  build_yolo
  clone_at chain-viz "$WS/chain-viz"
  (cd "$WS/chain-viz" && CARGO_TARGET_DIR="$WS/chain-viz/target" cargo build -q --release --locked)
  cp "$YOLO_BIN" "$WS/chain-viz/target/release/chain-viz" "$1/"
  "$1/yolo" --version
  "$1/chain-viz" --version
}

cmd_node_shard() {
  [ $# -eq 3 ] || die "usage: node-shard SUITE SHARD OF"
  need_ws
  local suite=$1 n=$2 of=$3 tree="$WS/ycash6" zmq=() name flags=()
  local out="$RC_OUT/node-suites/$suite-$n"
  mkdir -p "$out/tmp"
  # configure's tests_config.ini for this tree (no build here: the binaries are the package's).
  "$tree/src/ycashd" --help 2>/dev/null | grep -q -- '-zmqpub' || zmq=(--no-zmq)
  python3 "$here/rc-suites.py" config "$tree/qa/pull-tester/tests_config.ini.in" "$tree" ${zmq[@]+"${zmq[@]}"} \
    > "$tree/qa/pull-tester/tests_config.ini"
  local list sel=()
  list=$(python3 "$here/rc-suites.py" lists "$tree/.github/workflows/yellowback-tests.yml" "$suite" "$n" "$of") \
    || die "no shard $n/$of of $suite in $tree's yellowback-tests.yml"
  while IFS= read -r name; do [ -n "$name" ] && sel+=("$name"); done <<<"$list"   # bash 3.2 too (no mapfile)
  [ "${#sel[@]}" -gt 0 ] || die "shard $n/$of of $suite is empty"
  [ "$suite" = yellowback ] && flags=(--nozmq)
  # The same early, named failures as the node's own job: a script that would SKIP fails instead.
  for name in "${sel[@]}"; do
    case "$name" in
      yellowback_stratum)  [ -x "${YOLO_BIN:-}" ]     || die "no yolo (sidecars); $name would SKIP" ;;
      yellowback_chainviz) [ -x "${CHAINVIZ_BIN:-}" ] || die "no chain-viz (sidecars); $name would SKIP" ;;
      vault_pq_reorg)
        (cd "$tree" && python3 -c 'import sys; sys.path.insert(0, "qa/rpc-tests")
from test_framework import pq
sys.exit(0 if pq.falcon_signer_available() else 1)') || die "the Falcon signer does not build; $name would SKIP" ;;
    esac
  done
  echo "shard $n/$of of $suite against $("$tree/src/ycashd" --version | head -1): ${sel[*]}"
  (cd "$tree" && TMPDIR="$out/tmp" qa/pull-tester/rpc-tests.py --fail-on-skip -j4 ${flags[@]+"${flags[@]}"} --nocleanup "${sel[@]}")
}

devnet_down() { "$PY" "$DEVNET" down --dir "$1" >/dev/null 2>&1 || true; }

cmd_walk() {
  need_ws
  local dir="$RC_OUT/walk/devnet" q
  mkdir -p "$RC_OUT/walk"
  attest_agent
  build_yolo
  clone_at chain-viz "$WS/chain-viz"
  (cd "$WS/chain-viz" && CARGO_TARGET_DIR="$WS/chain-viz/target" cargo build -q --release --locked)
  export CHAINVIZ_BIN="$WS/chain-viz/target/release/chain-viz"
  lightwalletd
  printf -v q %q "$dir"
  # shellcheck disable=SC2064 # the devnet dir is fixed when the trap is set: the local is gone when EXIT fires
  trap "devnet_down $q" EXIT
  "$PY" "$DEVNET" up --role attestor --no-heartbeat --no-walk --no-sim --seed 480 --dir "$dir"
  "$PY" "$WS/ycash6/contrib/yellowback/devnet/upgrade-walk" --dir "$dir" \
    --transcript "$RC_OUT/walk/upgrade-walk-transcript.txt" --summary "$RC_OUT/walk/summary.json"
}

cmd_yew() {
  need_ws
  mkdir -p "$RC_OUT/yew"
  attest_agent
  lightwalletd
  clone_at yew "$WS/yew"
  # YEW's devnet scripts run the devnet tool from "$ws/ycash-dd"; on the release path that tool and its
  # binary are this release's (ycash6), so the name points at this tree.
  [ -e "$WS/ycash-dd" ] || ln -s "$WS/ycash6" "$WS/ycash-dd"
  export BITCOIND="$WS/ycash6/src/ycashd" ZCASHD="$WS/ycash6/src/ycashd" YEW_DEVNET_TOOL="$DEVNET" YEW_DEVNET_PYTHON="$PY"
  local suite rc=0
  for suite in w1 w2 w4 falcon pqaddr; do
    echo "== YEW $suite"
    # shellcheck disable=SC2064 # the suite's name is fixed when the trap is set, on purpose
    if (cd "$WS/yew" && trap "scripts/devnet-$suite.sh down || true" EXIT && scripts/devnet-$suite.sh up && scripts/devnet-$suite.sh test) \
        > "$RC_OUT/yew/$suite.log" 2>&1; then
      echo "ok   YEW $suite"
    else
      echo "FAIL YEW $suite (see $RC_OUT/yew/$suite.log)"; tail -n 40 "$RC_OUT/yew/$suite.log"; rc=1
    fi
  done
  return "$rc"
}

cmd_x402() {
  need_ws
  mkdir -p "$RC_OUT/x402"
  clone_at x402-ycash "$WS/x402-ycash"
  build_yolo        # its stratum tests start yolo beside a pool node (devnet `pool N stratum start`)
  local seed=181
  export YELLOWBACK_WORKSPACE="$WS" PYTHON="$PY" YCASH6="$WS/ycash6" X402_SCRATCH="$RC_OUT/x402/scratch"
  (cd "$WS/x402-ycash" && npm ci --ignore-scripts)
  (
    cd "$WS/x402-ycash"
    trap 'scripts/devnet.sh down 6 "$seed" || true' EXIT
    scripts/devnet.sh up 6 "$seed"
    X402_DEVNET_JSON="$X402_SCRATCH/6-$seed/devnet.json" npm run test:devnet
  )
}

cmd_hawkeye() {
  need_ws
  mkdir -p "$RC_OUT/hawkeye"
  clone_at hawkeye "$WS/hawkeye"
  (cd "$WS/hawkeye" && CARGO_TARGET_DIR="$WS/hawkeye/target" cargo build -q --locked --bin hawkeye)
  (cd "$WS/hawkeye/eth" && npm ci --ignore-scripts && ./tools/fetch-wyec.sh)
  export YCASHD="$WS/ycash6/src/ycashd" YCASH_CLI="$WS/ycash6/src/ycash-cli" DEVNET_NATIVE_SOLC=1
  (
    cd "$WS/hawkeye"
    trap 'python3 devnet/hawkeye-devnet down || true' EXIT
    python3 devnet/hawkeye-devnet scenario demo --fresh --foreign ethereum
  )
}

cmd_yecwallet() {
  need_ws
  mkdir -p "$RC_OUT/yecwallet"
  attest_agent      # the default devnet runs the attestors' agents
  clone_at yecwallet-dd "$WS/yecwallet-dd"
  (cd "$WS/yecwallet-dd" && cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release && ninja -C build yellowback_test nodecompat_test)
  local dir="$RC_OUT/yecwallet/devnet" q
  printf -v q %q "$dir"
  # shellcheck disable=SC2064 # the devnet dir is fixed when the trap is set: the local is gone when EXIT fires
  trap "devnet_down $q" EXIT
  "$PY" "$DEVNET" up --dir "$dir" --portseed 7 --bitcoind "$WS/ycash6/src/ycashd" --no-viz
  (cd "$WS/yecwallet-dd" && QT_QPA_PLATFORM=offscreen YELLOWBACK_DEVNET_DIR="$dir" build/bin/yellowback_test \
    && QT_QPA_PLATFORM=offscreen YELLOWBACK_DEVNET_DIR="$dir" build/bin/nodecompat_test)
}

cmd_cross_line() {
  [ $# -eq 1 ] || die "usage: cross-line DD_TREE"
  need_ws
  local dd=$1 dir="$RC_OUT/cross-line/devnet" q
  [ -x "$dd/src/ycashd" ] || die "no ycash-dd ycashd at $dd/src/ycashd"
  mkdir -p "$RC_OUT/cross-line"
  attest_agent
  printf -v q %q "$dir"
  # shellcheck disable=SC2064 # the devnet dir is fixed when the trap is set: the local is gone when EXIT fires
  trap "devnet_down $q" EXIT
  # The default devnet (attestor set ARMED, personas on), mined by the driver rather than the heartbeat,
  # so every node stands on the same tip when the digests are read.
  "$PY" "$DEVNET" up --no-heartbeat --no-walk --no-viz --dir "$dir"
  "$PY" "$here/rc-crossline.py" --devnet-dir "$dir" --dd-ycashd "$dd/src/ycashd" --framework "$WS/ycash6/qa/rpc-tests" \
    --dd-nodes 2 --rounds "${CROSSLINE_ROUNDS:-5}" --out "$RC_OUT/cross-line/digests.json"
}

cmd_ceremony() {
  need_ws
  local tool="$WS/ycash6/contrib/testnet/ceremony/ceremony" profile
  # testnet plan §2.2 / N2: the ceremony is a script with a regtest rehearsal. Its entry point here is
  # `ceremony rehearse --profile P --dir D --bitcoind B`, the interface N2 is asked to provide.
  [ -x "$tool" ] || die "this tag carries no $tool (testnet plan N2): step 4 cannot run"
  for profile in fast slow; do
    mkdir -p "$RC_OUT/ceremony/$profile"
    "$PY" "$tool" rehearse --profile "$profile" --dir "$RC_OUT/ceremony/$profile/run" \
      --bitcoind "$WS/ycash6/src/ycashd" | tee "$RC_OUT/ceremony/$profile/transcript.txt"
  done
}

[ $# -ge 1 ] || { sed -n '/^# Usage:/,/^set -euo/p' "$0" | sed '$d' >&2; exit 2; }
command=$1; shift
case "$command" in
  install)    cmd_install "$@" ;;
  train)      cmd_train "$@" ;;
  sidecars)   cmd_sidecars "$@" ;;
  node-shard) cmd_node_shard "$@" ;;
  pins)       cmd_pins "$@" ;;
  walk)       cmd_walk ;;
  yew)        cmd_yew ;;
  x402)       cmd_x402 ;;
  hawkeye)    cmd_hawkeye ;;
  yecwallet)  cmd_yecwallet ;;
  cross-line) cmd_cross_line "$@" ;;
  ceremony)   cmd_ceremony ;;
  *) die "unknown command $command" ;;
esac
