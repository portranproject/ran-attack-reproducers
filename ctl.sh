#!/usr/bin/env bash
# 격리 테스트베드의 공격 재현 모듈을 한 곳에서 준비하고 실행한다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACKS=(rrc-storm blind-dos uplink-dos auth-timeout downlink-imsi ue-capability)

fail() { echo "ctl.sh: $*" >&2; exit 2; }

attack_id() {
  case ${1:-} in
    rrc-storm|rrc-signaling-storm|rrc) echo rrc-storm ;;
    blind-dos|blind) echo blind-dos ;;
    uplink-dos|uplink) echo uplink-dos ;;
    auth-timeout|authentication-timeout-exhaustion|auth) echo auth-timeout ;;
    downlink-imsi|downlink-imsi-extractor|downlink) echo downlink-imsi ;;
    ue-capability|ue-capability-hijacking|capability) echo ue-capability ;;
    *) return 1 ;;
  esac
}

attack_label() {
  case $1 in
    rrc-storm) echo "RRCSetupComplete 미전송형" ;;
    blind-dos) echo "현재 유효 5G-GUTI 재사용형 Blind DoS" ;;
    uplink-dos) echo "상향 DoS 프로토콜 영향 에뮬레이션" ;;
    auth-timeout) echo "인증 응답 미전송형 연결 컨텍스트 고갈 (NAS 고갈)" ;;
    downlink-imsi) echo "하향 IMSI 추출 결과 에뮬레이션" ;;
    ue-capability) echo "보안 전 UE Capability Information 주입" ;;
  esac
}

attack_kind() {
  case $1 in
    rrc-storm|blind-dos|auth-timeout) echo "프로토콜 재현" ;;
    uplink-dos|downlink-imsi) echo "프로토콜 결과 에뮬레이션" ;;
    ue-capability) echo "프로토콜 관측 에뮬레이션" ;;
  esac
}

module_dir() {
  case $1 in
    rrc-storm) echo "$ROOT/reproducers/rrc-signaling-storm" ;;
    blind-dos) echo "$ROOT/reproducers/blind-dos" ;;
    uplink-dos) echo "$ROOT/reproducers/uplink-dos" ;;
    auth-timeout) echo "$ROOT/reproducers/authentication-timeout-exhaustion" ;;
    downlink-imsi) echo "$ROOT/reproducers/downlink-imsi-extractor" ;;
    ue-capability) echo "$ROOT/reproducers/ue-capability-hijacking" ;;
  esac
}

config_file() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "$dir/conf/rss.conf" ;;
    blind-dos) echo "$dir/conf/blind.conf" ;;
    uplink-dos) echo "$dir/conf/uplink.conf" ;;
    auth-timeout) echo "$dir/conf/auth-timeout.conf" ;;
    downlink-imsi) echo "$dir/conf/downlink-imsi.conf" ;;
    ue-capability) echo "$dir/conf/ue-capability.conf" ;;
  esac
}

config_example() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "$dir/conf/rss.conf.example" ;;
    blind-dos) echo "$dir/conf/p5-zmq.conf.example" ;;
    uplink-dos) echo "$dir/conf/uplink.conf.example" ;;
    auth-timeout) echo "$dir/conf/auth-timeout.conf.example" ;;
    downlink-imsi) echo "$dir/conf/p5-zmq.conf.example" ;;
    ue-capability) echo "$dir/conf/p5-zmq.conf.example" ;;
  esac
}

oai_tree() {
  case $1 in
    rrc-storm) echo "${RRC_OAI:-${OAI_BASE:-/root/OAI}}" ;;
    blind-dos) echo "${BLIND_OAI:-/root/OAI-blind-dos-w38}" ;;
    uplink-dos) echo "${UPLINK_OAI:-/root/OAI-uplink-dos-w38}" ;;
    auth-timeout) echo "${AUTH_TIMEOUT_OAI:-/root/OAI-auth-timeout-w38}" ;;
    downlink-imsi) echo "${DOWNLINK_IMSI_OAI:-/root/OAI-downlink-imsi-w38}" ;;
    ue-capability) echo "${UE_CAPABILITY_OAI:-/root/OAI-ue-capability-w38}" ;;
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
    auth-timeout) echo 'AUTH_TIMEOUT_EXHAUSTION event=authentication_request_withheld' ;;
    downlink-imsi) echo 'DOWNLINK_IMSI_EXTRACTOR event=identity_response_substituted' ;;
    ue-capability) echo 'UE_CAPABILITY_INJECTION event=%s' ;;
  esac
}

ue_binary() { echo "$(oai_tree "$1")/cmake_targets/ran_build/build/nr-uesoftmodem"; }

is_built() {
  local binary marker
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
      uplink-dos) OAI="$tree" "$dir/bin/uplink-build" ;;
      auth-timeout) OAI="$tree" "$dir/bin/auth-timeout-build" ;;
      downlink-imsi) OAI="$tree" "$dir/bin/downlink-imsi-build" ;;
      ue-capability) OAI="$tree" "$dir/bin/ue-capability-build" ;;
    esac
  fi
  is_built "$attack" || fail "빌드 산출물에서 모듈 마커를 확인하지 못했습니다"
}

setup_one() {
  prepare_config "$1"
  build_one "$1"
}

doctor_one() {
  local attack=$1 config failed=0
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
    uplink-dos) echo UPLINK_CONF ;;
    auth-timeout) echo AUTH_TIMEOUT_CONF ;;
    downlink-imsi) echo DOWNLINK_IMSI_CONF ;;
    ue-capability) echo UE_CAPABILITY_CONF ;;
  esac
}

run_binary() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    rrc-storm) echo "$dir/bin/rss-run" ;;
    blind-dos) echo "$dir/bin/blind-run" ;;
    uplink-dos) echo "$dir/bin/uplink-run" ;;
    auth-timeout) echo "$dir/bin/auth-timeout-run" ;;
    downlink-imsi) echo "$dir/bin/downlink-imsi-run" ;;
    ue-capability) echo "$dir/bin/ue-capability-run" ;;
  esac
}

campaign_binary() {
  local dir; dir=$(module_dir "$1")
  case $1 in
    blind-dos) echo "$dir/bin/blind-campaign" ;;
    uplink-dos) echo "$dir/bin/uplink-campaign" ;;
    auth-timeout) echo "$dir/bin/auth-timeout-campaign" ;;
    downlink-imsi) echo "$dir/bin/downlink-imsi-campaign" ;;
    ue-capability) echo "$dir/bin/ue-capability-campaign" ;;
    *) return 1 ;;
  esac
}

active_mode() {
  case $1 in
    rrc-storm|blind-dos|auth-timeout) echo attack ;;
    uplink-dos|downlink-imsi|ue-capability) echo emulation ;;
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
  local attack=$1 mode=$2 run_id=$3 enabled=$4 dry_run=$5
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
  local attack=$1 campaign_id=$2 enabled=$3 dry_run=$4
  local config env_name runner
  local -a command
  [[ $attack != rrc-storm ]] || fail "동결된 RRC 모듈에는 공통 3세트 캠페인이 없습니다"
  valid_run_id "$campaign_id" || fail "CAMPAIGN_ID가 안전하지 않습니다"
  [[ $enabled == 1 ]] || fail "캠페인에는 명시적 --enable이 필요합니다"
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
  printf '%-16s %-28s %s\n' ID 유형 이름
  local attack
  for attack in "${ATTACKS[@]}"; do
    printf '%-16s %-28s %s\n' "$attack" "$(attack_kind "$attack")" "$(attack_label "$attack")"
  done
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
          if [[ $choice == rrc-storm ]]; then echo "RRC 공통 캠페인은 지원하지 않습니다"; break; fi
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
  ./ctl.sh run ID MODE RUN_ID [--enable] [--dry-run]
  ./ctl.sh campaign ID CAMPAIGN_ID --enable [--dry-run]

ID: rrc-storm, blind-dos, uplink-dos, auth-timeout, downlink-imsi, ue-capability
MODE: control 또는 목록에 맞는 attack/emulation

setup은 현재 p5 경로를 기본값으로 사용한다. 다른 호스트에서는 OAI_BASE와
RRC_OAI/BLIND_OAI/UPLINK_OAI/AUTH_TIMEOUT_OAI/DOWNLINK_IMSI_OAI/UE_CAPABILITY_OAI를 지정한다.
EOF
}

main() {
  local subcommand=${1:-menu} target attack mode run_id enabled=0 dry_run=0 option
  case $subcommand in
    menu) menu ;;
    list) list_attacks ;;
    doctor)
      command -v git >/dev/null && command -v python3 >/dev/null \
        || fail "git과 python3가 필요합니다"
      doctor_targets "${2:-all}" ;;
    setup) [[ $# == 2 ]] || fail "setup은 ID 또는 all 하나가 필요합니다"; for_each_strict setup_one "$2" ;;
    build) [[ $# == 2 ]] || fail "build는 ID 또는 all 하나가 필요합니다"; for_each_strict build_one "$2" ;;
    run)
      [[ $# -ge 4 ]] || fail "run은 ID MODE RUN_ID가 필요합니다"
      attack=$(attack_id "$2") || fail "알 수 없는 공격 ID: $2"
      mode=$3
      run_id=$4
      shift 4
      for option in "$@"; do
        case $option in --enable) enabled=1 ;; --dry-run) dry_run=1 ;; *) fail "알 수 없는 옵션: $option" ;; esac
      done
      run_one "$attack" "$mode" "$run_id" "$enabled" "$dry_run"
      ;;
    campaign)
      [[ $# -ge 3 ]] || fail "campaign은 ID CAMPAIGN_ID가 필요합니다"
      attack=$(attack_id "$2") || fail "알 수 없는 공격 ID: $2"
      target=$3
      shift 3
      for option in "$@"; do
        case $option in --enable) enabled=1 ;; --dry-run) dry_run=1 ;; *) fail "알 수 없는 옵션: $option" ;; esac
      done
      campaign_one "$attack" "$target" "$enabled" "$dry_run"
      ;;
    -h|--help|help) usage ;;
    *) usage; fail "알 수 없는 명령: $subcommand" ;;
  esac
}

main "$@"
