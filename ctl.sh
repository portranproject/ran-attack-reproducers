#!/usr/bin/env bash
# 격리 테스트베드의 공격 재현 모듈을 한 곳에서 준비하고 실행한다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACKS=(
  rrc-storm blind-dos uplink-dos uplink-credential-flood auth-timeout downlink-imsi ue-capability
  nas-counter-desynchronization authentication-sync-failure nas-counter-reset
  uplink-identifier-exposure short-connection-repeat rrc-reject-release-imprisonment tac-manipulation-return
)
REPROCTL="$ROOT/tools/reproctl.py"
NORMAL_UE="$ROOT/workloads/normal-ue/bin/normal-ue"
SAME_CELL="$ROOT/workloads/normal-ue/bin/same-cell-run"

fail() { echo "ctl.sh: $*" >&2; exit 2; }

attack_id() {
  case ${1:-} in
    rrc-storm|rrc-signaling-storm|rrc-context-exhaustion|rrc) echo rrc-storm ;;
    blind-dos|blind) echo blind-dos ;;
    uplink-dos|uplink) echo uplink-dos ;;
    uplink-credential-flood|credential-flood|uplink-l3-21) echo uplink-credential-flood ;;
    auth-timeout|authentication-timeout-exhaustion|auth) echo auth-timeout ;;
    downlink-imsi|downlink-imsi-extractor|downlink-identifier-exposure|downlink) echo downlink-imsi ;;
    ue-capability|ue-capability-hijacking|capability) echo ue-capability ;;
    nas-counter-desynchronization|l3-06) echo nas-counter-desynchronization ;;
    authentication-sync-failure|an-01) echo authentication-sync-failure ;;
    nas-counter-reset|an-06a) echo nas-counter-reset ;;
    uplink-identifier-exposure|uplink-imsi|an-02) echo uplink-identifier-exposure ;;
    short-connection-repeat|an-04) echo short-connection-repeat ;;
    rrc-reject-release-imprisonment|an-07) echo rrc-reject-release-imprisonment ;;
    tac-manipulation-return|an-08) echo tac-manipulation-return ;;
    *) return 1 ;;
  esac
}

attack_label() {
  case $1 in
    rrc-storm) echo "RRCSetupComplete 미전송형" ;;
    blind-dos) echo "현재 유효 5G-GUTI 재사용형 Blind DoS" ;;
    uplink-dos) echo "상향 DoS 프로토콜 영향 에뮬레이션" ;;
    uplink-credential-flood) echo "무효·위조 자격증명 플러드형 상향 DoS" ;;
    auth-timeout) echo "인증 응답 미전송형 연결 컨텍스트 고갈 (NAS 고갈)" ;;
    downlink-imsi) echo "하향 IMSI 추출 결과 에뮬레이션" ;;
    ue-capability) echo "보안 전 UE Capability Information 주입" ;;
    nas-counter-desynchronization) echo "NAS 카운터 비동기화 결과 에뮬레이션" ;;
    authentication-sync-failure) echo "인증 동기 실패" ;;
    nas-counter-reset) echo "NAS 카운터 reset 계열 재인증" ;;
    uplink-identifier-exposure) echo "GUTI 불일치 후 상향 식별자 요청 결과" ;;
    short-connection-repeat) echo "짧은 RRC 연결 반복" ;;
    rrc-reject-release-imprisonment) echo "RRC 거절·해제 투옥 계열 미완료 반복" ;;
    tac-manipulation-return) echo "TAC 조작·가짜 기지국 복귀 신호" ;;
  esac
}

attack_kind() {
  case $1 in
    rrc-storm|blind-dos|auth-timeout) echo "프로토콜 재현" ;;
    uplink-dos|downlink-imsi) echo "프로토콜 결과 에뮬레이션" ;;
    uplink-credential-flood) echo "프로토콜 재현" ;;
    ue-capability) echo "프로토콜 관측 에뮬레이션" ;;
    nas-counter-desynchronization) echo "프로토콜 결과 에뮬레이션" ;;
    authentication-sync-failure|nas-counter-reset|uplink-identifier-exposure|short-connection-repeat|rrc-reject-release-imprisonment|tac-manipulation-return)
      echo "탐지 입력 에뮬레이션" ;;
  esac
}

module_dir() {
  case $1 in
    rrc-storm) echo "$ROOT/reproducers/rrc-signaling-storm" ;;
    blind-dos) echo "$ROOT/reproducers/blind-dos" ;;
    uplink-dos|uplink-credential-flood) echo "$ROOT/reproducers/uplink-dos" ;;
    auth-timeout) echo "$ROOT/reproducers/authentication-timeout-exhaustion" ;;
    downlink-imsi) echo "$ROOT/reproducers/downlink-imsi-extractor" ;;
    ue-capability) echo "$ROOT/reproducers/ue-capability-hijacking" ;;
    uplink-identifier-exposure) echo "$ROOT/reproducers/uplink-imsi-extractor" ;;
    nas-counter-desynchronization|authentication-sync-failure|nas-counter-reset|short-connection-repeat|rrc-reject-release-imprisonment|tac-manipulation-return)
      echo "$ROOT/reproducers/$1" ;;
  esac
}

is_common_signal() {
  case $1 in
    authentication-sync-failure|nas-counter-reset|uplink-identifier-exposure|short-connection-repeat|rrc-reject-release-imprisonment|tac-manipulation-return) return 0 ;;
    *) return 1 ;;
  esac
}

load_profile_env() {
  local profile=$1 line output
  output=$(python3 "$REPROCTL" env --profile "$profile") || fail "profile을 불러오지 못했습니다: $profile"
  while IFS= read -r line; do export "$line"; done <<<"$output"
}

require_runnable_backend() {
  [[ ${RAN_REPRO_BACKEND:-} != ota ]] \
    || fail "OTA 실행 adapter는 아직 미구현입니다. PORTING-GUIDE.md의 OTA 포팅 절차를 먼저 완료해야 합니다"
}

config_file() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "${RSS_CONF:-$dir/conf/rss.conf}" ;;
    blind-dos) echo "${BLIND_CONF:-$dir/conf/blind.conf}" ;;
    uplink-dos|uplink-credential-flood) echo "${UPLINK_CONF:-$dir/conf/uplink.conf}" ;;
    auth-timeout) echo "${AUTH_TIMEOUT_CONF:-$dir/conf/auth-timeout.conf}" ;;
    downlink-imsi) echo "${DOWNLINK_IMSI_CONF:-$dir/conf/downlink-imsi.conf}" ;;
    ue-capability) echo "${UE_CAPABILITY_CONF:-$dir/conf/ue-capability.conf}" ;;
    nas-counter-desynchronization) echo "${NAS_DESYNC_CONF:-$dir/conf/nas-counter-desync.conf}" ;;
  esac
}

config_example() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "$dir/conf/rss.conf.example" ;;
    blind-dos) echo "$dir/conf/p5-zmq.conf.example" ;;
    uplink-dos|uplink-credential-flood) echo "$dir/conf/uplink.conf.example" ;;
    auth-timeout) echo "$dir/conf/auth-timeout.conf.example" ;;
    downlink-imsi) echo "$dir/conf/p5-zmq.conf.example" ;;
    ue-capability) echo "$dir/conf/p5-zmq.conf.example" ;;
    nas-counter-desynchronization) echo "$dir/conf/nas-counter-desync.conf.example" ;;
  esac
}

oai_tree() {
  case $1 in
    rrc-storm) echo "${RRC_OAI:-${OAI_BASE:-/root/OAI}}" ;;
    blind-dos) echo "${BLIND_OAI:-/root/OAI-blind-dos-w38}" ;;
    uplink-dos|uplink-credential-flood) echo "${UPLINK_OAI:-/root/OAI-uplink-dos-w38}" ;;
    auth-timeout) echo "${AUTH_TIMEOUT_OAI:-/root/OAI-auth-timeout-w38}" ;;
    downlink-imsi) echo "${DOWNLINK_IMSI_OAI:-/root/OAI-downlink-imsi-w38}" ;;
    ue-capability) echo "${UE_CAPABILITY_OAI:-/root/OAI-ue-capability-w38}" ;;
    nas-counter-desynchronization) echo "${NAS_DESYNC_OAI:-/root/OAI-nas-desync-w38}" ;;
  esac
}

oai_commit() {
  case $1 in
    rrc-storm) echo 1c2f4d3c2e68181cdef9f426d161163147ad4b77 ;;
    *) echo 6d6782b48484efd935c14e834832032743f9b138 ;;
  esac
}

built_marker() {
  case $1 in
    rrc-storm) echo target_occupancy ;;
    blind-dos) echo target_5g_s_tmsi ;;
    uplink-dos) echo 'UPLINK_DOS_EMULATION event=service_request_mac_corrupted' ;;
    uplink-credential-flood) echo 'UPLINK_DOS_DETECTION event=registration_failure' ;;
    auth-timeout) echo 'AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld' ;;
    downlink-imsi) echo 'DOWNLINK_IMSI_EXTRACTOR event=identity_response_substituted' ;;
    ue-capability) echo 'UE_CAPABILITY_INJECTION event=%s' ;;
    nas-counter-desynchronization) echo 'NAS_COUNTER_DESYNC event=unsolicited_security_mode_reject' ;;
  esac
}

ue_binary() { echo "$(oai_tree "$1")/cmake_targets/ran_build/build/nr-uesoftmodem"; }

is_built() {
  local binary marker
  if is_common_signal "$1"; then
    [[ -x $REPROCTL && -f $ROOT/tools/generate_rule_signal.py ]]
    return
  fi
  binary=$(ue_binary "$1")
  marker=$(built_marker "$1")
  [[ -x $binary ]] && grep -Faq "$marker" "$binary"
}

prepare_config() {
  local attack=$1 target source
  target=$(config_file "$attack")
  source=$(config_example "$attack")
  [[ ! -L $target ]] || fail "설정 파일이 심볼릭 링크입니다: $target"
  if [[ -f $target ]]; then
    echo "설정 유지: $target"
    return
  fi
  [[ -f $source && ! -L $source ]] || fail "설정 예제가 없습니다: $source"
  install -m 600 "$source" "$target"
  echo "설정 생성: $target"
  echo "  랩 경로·가입자·키·해시 값을 실행 전에 검토해야 합니다."
}

ensure_worktree() {
  local attack=$1 target base commit head
  target=$(oai_tree "$attack")
  base=${OAI_BASE:-/root/OAI}
  commit=$(oai_commit "$attack")
  [[ -n $target && $target != / ]] || fail "안전하지 않은 OAI 경로입니다: $target"
  if git -C "$target" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    head=$(git -C "$target" rev-parse HEAD)
    [[ $head == "$commit" ]] || fail "$target HEAD가 기준 커밋과 다릅니다: $head"
    return
  fi
  git -C "$base" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || fail "기준 OAI 저장소가 없습니다: $base (OAI_BASE로 지정 가능)"
  if ! git -C "$base" cat-file -e "$commit^{commit}" 2>/dev/null; then
    echo "OAI 기준 커밋 가져오는 중: $commit"
    git -C "$base" fetch origin "$commit" \
      || fail "기준 커밋을 가져오지 못했습니다: $commit"
  fi
  mkdir -p "$(dirname "$target")"
  git -C "$base" worktree add --detach "$target" "$commit"
}

build_one() {
  local attack=$1 dir tree
  dir=$(module_dir "$attack")
  if is_common_signal "$attack"; then
    python3 "$REPROCTL" validate >/dev/null
    echo "도구 준비됨: $(attack_label "$attack") (OAI 빌드 없음)"
    return
  fi
  tree=$(oai_tree "$attack")
  if is_built "$attack"; then
    echo "빌드 준비됨: $(attack_label "$attack")"
    return
  fi
  echo "빌드 시작: $(attack_label "$attack")"
  if [[ $attack == rrc-storm ]]; then
    RSS_CONF=/dev/null OAI="$tree" "$dir/bin/rss-bootstrap"
    RSS_CONF=/dev/null OAI="$tree" "$dir/bin/rss-build"
  else
    ensure_worktree "$attack"
    case $attack in
      blind-dos) BLIND_CONF=/dev/null OAI="$tree" "$dir/bin/blind-build" ;;
      uplink-dos|uplink-credential-flood) OAI="$tree" "$dir/bin/uplink-build" ;;
      auth-timeout) OAI="$tree" "$dir/bin/auth-timeout-build" ;;
      downlink-imsi) OAI="$tree" "$dir/bin/downlink-imsi-build" ;;
      ue-capability) OAI="$tree" "$dir/bin/ue-capability-build" ;;
      nas-counter-desynchronization) OAI="$tree" "$dir/bin/nas-counter-desync-build" ;;
    esac
  fi
  is_built "$attack" || fail "빌드 산출물에서 모듈 마커를 확인하지 못했습니다"
}

setup_one() {
  if is_common_signal "$1"; then build_one "$1"; return; fi
  prepare_config "$1"
  build_one "$1"
}

doctor_one() {
  local attack=$1 config failed=0
  if is_common_signal "$attack"; then
    echo "[$attack] $(attack_label "$attack")"
    if is_built "$attack"; then echo "  OK 공통 탐지 입력 runner"; else echo "  필요 도구: $REPROCTL"; failed=1; fi
    return "$failed"
  fi
  config=$(config_file "$attack")
  echo "[$attack] $(attack_label "$attack")"
  if [[ -f $config && ! -L $config ]]; then
    echo "  OK 설정: $config (랩 값 검토는 별도)"
  else
    echo "  필요 설정: $config"
    failed=1
  fi
  if is_built "$attack"; then
    echo "  OK 빌드: $(ue_binary "$attack")"
  else
    echo "  필요 빌드: $(ue_binary "$attack")"
    failed=1
  fi
  return "$failed"
}

config_env() {
  case $1 in
    rrc-storm) echo RSS_CONF ;;
    blind-dos) echo BLIND_CONF ;;
    uplink-dos|uplink-credential-flood) echo UPLINK_CONF ;;
    auth-timeout) echo AUTH_TIMEOUT_CONF ;;
    downlink-imsi) echo DOWNLINK_IMSI_CONF ;;
    ue-capability) echo UE_CAPABILITY_CONF ;;
    nas-counter-desynchronization) echo NAS_DESYNC_CONF ;;
  esac
}

run_binary() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "$dir/bin/rss-run" ;;
    blind-dos) echo "$dir/bin/blind-run" ;;
    uplink-dos) echo "$dir/bin/uplink-run" ;;
    uplink-credential-flood) echo "$dir/bin/uplink-credential-flood-run" ;;
    auth-timeout) echo "$dir/bin/auth-timeout-run" ;;
    downlink-imsi) echo "$dir/bin/downlink-imsi-run" ;;
    ue-capability) echo "$dir/bin/ue-capability-run" ;;
    nas-counter-desynchronization) echo "$dir/bin/nas-counter-desync-run" ;;
  esac
}

campaign_binary() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    blind-dos) echo "$dir/bin/blind-campaign" ;;
    uplink-dos) echo "$dir/bin/uplink-campaign" ;;
    uplink-credential-flood) echo "$dir/bin/uplink-credential-flood-campaign" ;;
    auth-timeout) echo "$dir/bin/auth-timeout-campaign" ;;
    downlink-imsi) echo "$dir/bin/downlink-imsi-campaign" ;;
    ue-capability) echo "$dir/bin/ue-capability-campaign" ;;
    nas-counter-desynchronization) echo "$dir/bin/nas-counter-desync-campaign" ;;
    *) return 1 ;;
  esac
}

active_mode() {
  case $1 in
    rrc-storm|blind-dos|auth-timeout) echo attack ;;
    uplink-credential-flood) echo attack ;;
    uplink-dos|downlink-imsi|ue-capability) echo emulation ;;
    nas-counter-desynchronization|authentication-sync-failure|nas-counter-reset|uplink-identifier-exposure|short-connection-repeat|rrc-reject-release-imprisonment|tac-manipulation-return) echo emulation ;;
  esac
}

valid_run_id() {
  [[ $1 =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ ]]
}

print_command() {
  printf '실행 예정:'
  printf ' %q' "$@"
  printf '\n'
}

run_one() {
  local attack=$1 mode=$2 run_id=$3 enabled=$4 dry_run=$5 profile=${6:-p5}
  local expected config env_name runner enable_value
  local -a command
  expected=$(active_mode "$attack")
  [[ $mode == control || $mode == "$expected" ]] \
    || fail "$attack 모드는 control 또는 $expected 이어야 합니다"
  valid_run_id "$run_id" || fail "RUN_ID는 영문·숫자로 시작하고 ._-만 사용해야 합니다"
  if [[ $attack == rrc-storm && ${run_id:1:1} == O ]]; then
    fail "RRC RUN_ID의 두 번째 문자는 O일 수 없습니다(OAI 파서 제한)"
  fi
  if [[ $mode == control ]]; then
    [[ $enabled == 0 ]] || fail "control에는 --enable을 붙이지 않습니다"
    enable_value=0
  else
    [[ $enabled == 1 ]] || fail "$mode 실행에는 명시적 --enable이 필요합니다"
    enable_value=1
  fi
  if is_common_signal "$attack"; then
    command=(python3 "$REPROCTL" signal-run "$attack" "$mode" "$run_id" --profile "$profile")
    [[ $enabled == 1 ]] && command+=(--enable)
    if [[ $dry_run == 1 ]]; then print_command "${command[@]}"; return; fi
    exec "${command[@]}"
  fi
  config=$(config_file "$attack")
  env_name=$(config_env "$attack")
  runner=$(run_binary "$attack")
  if [[ $attack == rrc-storm ]]; then
    command=(env "$env_name=$config" "$runner" -n "$run_id" -e "$enable_value")
  else
    command=(env "$env_name=$config" "$runner" "$mode" -n "$run_id" -e "$enable_value")
  fi
  if [[ $dry_run == 1 ]]; then print_command "${command[@]}"; return; fi
  [[ -f $config && ! -L $config ]] || fail "설정이 없습니다. 먼저 실행: ./ctl.sh setup $attack"
  [[ -x $runner ]] || fail "runner가 없습니다: $runner"
  exec "${command[@]}"
}

campaign_one() {
  local attack=$1 campaign_id=$2 enabled=$3 dry_run=$4 profile=${5:-p5}
  local config env_name runner
  local -a command
  valid_run_id "$campaign_id" || fail "CAMPAIGN_ID가 안전하지 않습니다"
  [[ $enabled == 1 ]] || fail "캠페인에는 명시적 --enable이 필요합니다"
  if is_common_signal "$attack"; then
    command=(python3 "$REPROCTL" signal-campaign "$attack" "$campaign_id" --profile "$profile" --enable)
    if [[ $dry_run == 1 ]]; then print_command "${command[@]}"; return; fi
    exec "${command[@]}"
  fi
  if [[ $attack == rrc-storm ]]; then
    config=$(config_file "$attack")
    runner=$(run_binary "$attack")
    if [[ $dry_run == 1 ]]; then
      print_command env "RSS_CONF=$config" "$runner" -n "$campaign_id-control-1" -e 0
      print_command env "RSS_CONF=$config" "$runner" -n "$campaign_id-attack-1" -e 1
      echo "위 control→attack을 set 1..3으로 반복"
      return
    fi
    [[ -f $config && ! -L $config ]] || fail "설정이 없습니다. 먼저 실행: ./ctl.sh setup $attack"
    [[ -x $runner ]] || fail "runner가 없습니다: $runner"
    local index
    for index in 1 2 3; do
      env "RSS_CONF=$config" "$runner" -n "$campaign_id-control-$index" -e 0
      env "RSS_CONF=$config" "$runner" -n "$campaign_id-attack-$index" -e 1
    done
    return
  fi
  config=$(config_file "$attack")
  env_name=$(config_env "$attack")
  runner=$(campaign_binary "$attack")
  command=(env "$env_name=$config" "$runner" -n "$campaign_id" -e 1)
  if [[ $dry_run == 1 ]]; then print_command "${command[@]}"; return; fi
  [[ -f $config && ! -L $config ]] || fail "설정이 없습니다. 먼저 실행: ./ctl.sh setup $attack"
  [[ -x $runner ]] || fail "campaign runner가 없습니다: $runner"
  exec "${command[@]}"
}

list_attacks() {
  python3 "$REPROCTL" catalog
  printf '%-32s %-12s %-30s %s\n' uplink-dos legacy protocol-result-emulation "상향 DoS 단발 MAC 변조 결과 에뮬레이션"
}

for_each_strict() {
  local action=$1 target=$2 attack
  if [[ $target == all ]]; then
    for attack in "${ATTACKS[@]}"; do "$action" "$attack"; done
  else
    attack=$(attack_id "$target") || fail "알 수 없는 공격 ID: $target"
    "$action" "$attack"
  fi
}

doctor_targets() {
  local target=$1 attack failed=0
  if [[ $target == all ]]; then
    for attack in "${ATTACKS[@]}"; do doctor_one "$attack" || failed=1; done
  else
    attack=$(attack_id "$target") || fail "알 수 없는 공격 ID: $target"
    doctor_one "$attack" || failed=1
  fi
  return "$failed"
}

menu() {
  echo "기지국 공격 재현 통합 컨트롤러"
  PS3="공격 번호 선택: "
  select choice in "${ATTACKS[@]}" 종료; do
    [[ $choice == 종료 ]] && return
    [[ -n $choice ]] || { echo "잘못된 선택입니다"; continue; }
    local label mode action run_id answer
    label=$(attack_label "$choice")
    mode=$(active_mode "$choice")
    echo "선택: $label ($(attack_kind "$choice"))"
    PS3="작업 번호 선택: "
    select action in 상태점검 환경준비_및_빌드 정상대조 "$mode" 3세트_캠페인 뒤로; do
      case $action in
        상태점검) doctor_one "$choice" || true; break ;;
        환경준비_및_빌드)
          read -r -p "설정 생성·OAI 준비·빌드를 시작하려면 SETUP 입력: " answer
          if [[ $answer == SETUP ]]; then setup_one "$choice"; else echo "취소됨"; fi
          break ;;
        정상대조)
          run_id="$choice-control-$(date -u +%Y%m%dT%H%M%SZ)"
          read -r -p "RUN_ID [$run_id]: " answer; run_id=${answer:-$run_id}
          run_one "$choice" control "$run_id" 0 0
          ;;
        "$mode")
          run_id="$choice-$mode-$(date -u +%Y%m%dT%H%M%SZ)"
          read -r -p "RUN_ID [$run_id]: " answer; run_id=${answer:-$run_id}
          read -r -p "격리 테스트베드임을 확인하려면 ENABLE 입력: " answer
          if [[ $answer == ENABLE ]]; then run_one "$choice" "$mode" "$run_id" 1 0; else echo "취소됨"; fi
          ;;
        3세트_캠페인)
          run_id="$choice-campaign-$(date -u +%Y%m%dT%H%M%SZ)"
          read -r -p "CAMPAIGN_ID [$run_id]: " answer; run_id=${answer:-$run_id}
          read -r -p "격리 테스트베드임을 확인하려면 ENABLE 입력: " answer
          if [[ $answer == ENABLE ]]; then campaign_one "$choice" "$run_id" 1 0; else echo "취소됨"; fi
          ;;
        뒤로) break ;;
        *) echo "잘못된 선택입니다" ;;
      esac
    done
  done
}

usage() {
  cat <<'EOF'
사용법:
  ./ctl.sh                         대화형 메뉴
  ./ctl.sh list                    공격 목록과 재현 유형
  ./ctl.sh doctor [ID|all]         설정·빌드 상태 확인
  ./ctl.sh setup ID|all            설정 생성 + 전용 OAI 준비 + 빌드
  ./ctl.sh build ID|all            이미 준비된 OAI에서 빌드
  ./ctl.sh run ID MODE RUN_ID [--profile p5|ota] [--enable] [--dry-run]
  ./ctl.sh campaign ID [CAMPAIGN_ID] [--profile p5|ota] --enable [--dry-run]
  ./ctl.sh replay RUN_ID --profile p5|ota
  ./ctl.sh report RUN_ID [--profile p5|ota]
  ./ctl.sh verify RUN_ID [--profile p5|ota]
  ./ctl.sh coverage
  ./ctl.sh validate
  ./ctl.sh normal-ue setup|doctor|start|status|stop [--profile p5] [--count N]
  ./ctl.sh same-cell run blind|uplink|uplink-credential-flood|auth-timeout|downlink-imsi|ue-capability|nas-counter-desync -n RUN_ID [--count 5] -- COMMAND...
  ./ctl.sh same-cell start -n SESSION_ID [--count 5]  # 정상 UE 개발 세션
  ./ctl.sh same-cell status|stop

ID 전체 목록: ./ctl.sh list
MODE: control 또는 목록에 맞는 attack/emulation

setup은 현재 p5 경로를 기본값으로 사용한다. 다른 호스트에서는 OAI_BASE와
RRC_OAI/BLIND_OAI/UPLINK_OAI/AUTH_TIMEOUT_OAI/DOWNLINK_IMSI_OAI/UE_CAPABILITY_OAI/NAS_DESYNC_OAI를 지정한다.
EOF
}

main() {
  local subcommand=${1:-menu} target attack mode run_id enabled=0 dry_run=0 option profile=p5 profile_given=0
  case $subcommand in
    menu) menu ;;
    list) list_attacks ;;
    coverage) python3 "$REPROCTL" coverage ;;
    validate) python3 "$REPROCTL" validate ;;
    normal-ue)
      [[ -x $NORMAL_UE ]] || fail "normal-ue runner가 없습니다: $NORMAL_UE"
      shift
      exec "$NORMAL_UE" "$@" ;;
    same-cell)
      [[ -x $SAME_CELL ]] || fail "same-cell runner가 없습니다: $SAME_CELL"
      shift
      exec "$SAME_CELL" "$@" ;;
    doctor)
      command -v git >/dev/null && command -v python3 >/dev/null \
        || fail "git과 python3가 필요합니다"
      target=all
      shift
      while [[ $# -gt 0 ]]; do
        case $1 in --profile) [[ $# -ge 2 ]] || fail "--profile 값이 필요합니다"; profile=$2; profile_given=1; shift 2 ;; *) target=$1; shift ;; esac
      done
      if [[ $profile_given == 1 ]]; then
        python3 "$REPROCTL" doctor --profile "$profile"
        load_profile_env "$profile"
        require_runnable_backend
      fi
      doctor_targets "$target" ;;
    setup|build)
      [[ $# -ge 2 ]] || fail "$subcommand는 ID 또는 all이 필요합니다"
      target=$2; shift 2
      while [[ $# -gt 0 ]]; do
        case $1 in --profile) [[ $# -ge 2 ]] || fail "--profile 값이 필요합니다"; profile=$2; profile_given=1; shift 2 ;; *) fail "알 수 없는 옵션: $1" ;; esac
      done
      if [[ $profile_given == 1 ]]; then load_profile_env "$profile"; require_runnable_backend; fi
      if [[ $subcommand == setup ]]; then for_each_strict setup_one "$target"; else for_each_strict build_one "$target"; fi ;;
    run)
      [[ $# -ge 4 ]] || fail "run은 ID MODE RUN_ID가 필요합니다"
      attack=$(attack_id "$2") || fail "알 수 없는 공격 ID: $2"
      mode=$3
      run_id=$4
      shift 4
      while [[ $# -gt 0 ]]; do
        case $1 in --enable) enabled=1; shift ;; --dry-run) dry_run=1; shift ;; --profile) [[ $# -ge 2 ]] || fail "--profile 값이 필요합니다"; profile=$2; profile_given=1; shift 2 ;; *) fail "알 수 없는 옵션: $1" ;; esac
      done
      if [[ $profile_given == 1 ]] && ! is_common_signal "$attack"; then
        load_profile_env "$profile"
        require_runnable_backend
      fi
      run_one "$attack" "$mode" "$run_id" "$enabled" "$dry_run" "$profile"
      ;;
    campaign)
      [[ $# -ge 2 ]] || fail "campaign은 ID가 필요합니다"
      attack=$(attack_id "$2") || fail "알 수 없는 공격 ID: $2"
      if [[ ${3:-} == --* || -z ${3:-} ]]; then target="$attack-campaign-$(date -u +%Y%m%dT%H%M%SZ)"; shift 2; else target=$3; shift 3; fi
      while [[ $# -gt 0 ]]; do
        case $1 in --enable) enabled=1; shift ;; --dry-run) dry_run=1; shift ;; --profile) [[ $# -ge 2 ]] || fail "--profile 값이 필요합니다"; profile=$2; profile_given=1; shift 2 ;; *) fail "알 수 없는 옵션: $1" ;; esac
      done
      if [[ $profile_given == 1 ]] && ! is_common_signal "$attack"; then
        load_profile_env "$profile"
        require_runnable_backend
      fi
      campaign_one "$attack" "$target" "$enabled" "$dry_run" "$profile"
      ;;
    replay)
      [[ $# == 4 && $3 == --profile ]] || fail "replay RUN_ID --profile NAME 형식이 필요합니다"
      exec python3 "$REPROCTL" replay "$2" --profile "$4" ;;
    report|verify)
      [[ $# -ge 2 ]] || fail "$subcommand RUN_ID가 필요합니다"
      run_id=$2; shift 2
      if [[ $# -gt 0 ]]; then [[ $# == 2 && $1 == --profile ]] || fail "--profile NAME 형식이 필요합니다"; profile=$2; exec python3 "$REPROCTL" "$subcommand" "$run_id" --profile "$profile"; fi
      exec python3 "$REPROCTL" "$subcommand" "$run_id" ;;
    -h|--help|help) usage ;;
    *) usage; fail "알 수 없는 명령: $subcommand" ;;
  esac
}

main "$@"
