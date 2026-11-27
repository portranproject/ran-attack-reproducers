#!/usr/bin/env bash
# run.sh — PORTRAN ATTACKER
# DU에서 실행하는 사용자 진입점. 환경 → 공격 → 작업 순서로 공식 runner를 호출한다.
#
# [1] 배너는 빨강 계열 다섯 단계로 칠해 입체로 보이게 함.
#
#     글자 면(█)      위 줄은 밝게, 아래 줄은 짙게      RED_HIGHLIGHT > RED_BRIGHT > RED_MID
#     글자 테두리(╗║╚)  가장 어둡게. 면 뒤의 그림자로 보임   RED_SHADOW
#     기지국          안테나 블록은 면과 같은 단계, 철탑 선은 RED_DEEP
#
# [2] 공격 목록은 ./tools/reproctl.py catalog --json 에서 L3 7종만 읽음 (ctl.sh 를 source 하지 않음)
# [3] 실행은 ctl.sh 의 same-cell doctor / run / campaign l3-live 만 씀. 다른 실행 경로 없음
# [4] 공격 실행 중에는 위쪽에 공격 모션을 반복하고 아래쪽에 ctl.sh 출력을 실시간으로 흘림
#     (bash 5 이상·창 높이 31줄 이상일 때. 아니면 실행 전 인트로 모션 뒤 출력만 흘림)
#
# 화면은 bash 3.2+, 카탈로그·DU 설정 검증은 기존 python3 도구를 사용함
# 종료 코드: 0 q 로 나감, 1 입력이 끊김(EOF), 2 옵션 오류
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CTL="$ROOT/tools/ctl.sh"

usage() {
	cat <<'USAGE'
사용법: ./run.sh [옵션]

  DU에서 환경 → L3 공격 → 작업을 선택한다.
  DU 설정은 RAN_REPRO_PROFILE_ID, profiles/du.json, 유일한 준비 완료 설정 순서로 읽는다.
  가상 환경은 tools/ctl.sh의 공식 same-cell runner를 사용한다.
  실장비 메뉴는 USRP ↔ gNB 동작 모션을 제공한다. OTA 실행 adapter는 준비 중이다.

옵션:
  --no-anim       공격 애니메이션 끔 (실행 중 모션 포함)
  --dry-run       run·campaign 에 --dry-run 을 붙여 생성 명령만 확인함 (doctor 는 명령만 출력)
  --frames DIR    ZMQ·USRP 동작 모션의 프레임을 텍스트로 저장하고 끝남
  -h, --help      이 도움말

키: ↑/↓ 또는 숫자로 고르고 Enter. b 뒤로, q 나감
터미널이 아니거나 NO_COLOR 가 있으면 색·애니메이션 없이 번호 입력 메뉴로 동작함
USAGE
}

ANIM=1 DRY_RUN=0 FRAMES_DIR=""
TRANSPORT=zmq
while [ $# -gt 0 ]; do
	case "$1" in
	--no-anim) ANIM=0; shift ;;
	--dry-run) DRY_RUN=1; shift ;;
	--frames)
		[ $# -ge 2 ] || { echo "run.sh: --frames 에 디렉터리가 필요함" >&2; exit 2; }
		FRAMES_DIR=$2; shift 2 ;;
	-h|--help) usage; exit 0 ;;
	*) echo "run.sh: 알 수 없는 옵션: $1 (--help 참고)" >&2; exit 2 ;;
	esac
done

# 그림 글자를 글자 수로 자르고 붙이므로 UTF-8 로케일이 필요함
case "$(locale charmap 2>/dev/null)" in
UTF-8|utf8) ;;
*) for candidate in C.UTF-8 en_US.UTF-8; do
	if locale -a 2>/dev/null | grep -qix "${candidate/UTF-8/utf-\{0,1\}8}"; then export LC_ALL=$candidate; break; fi
   done ;;
esac

# 색과 화면 제어는 터미널에 직접 찍을 때만 씀. 파이프나 파일로 보내면 제어 문자가 글자로 남기 때문임
#   NO_COLOR 는 색을 끄는 관례 환경 변수임 (https://no-color.org)
if [ -t 1 ] && [ -t 0 ] && [ -z "${NO_COLOR:-}" ]; then
	TTY=1
	if [ "$(tput colors 2>/dev/null || echo 8)" -ge 256 ]; then
		RED_HIGHLIGHT=$'\033[38;5;203m'   # 빛을 받는 윗면
		RED_BRIGHT=$'\033[38;5;196m'      # 기본 면
		RED_MID=$'\033[38;5;160m'         # 아래쪽 면
		RED_DEEP=$'\033[38;5;124m'        # 철탑 선
		RED_SHADOW=$'\033[38;5;88m'       # 글자 테두리(그림자)
		CYAN=$'\033[38;5;44m'             # 정상 UE
		YELLOW=$'\033[38;5;220m'          # 경고·카운터
	else
		# 256색을 못 쓰는 터미널은 밝은 빨강과 보통 빨강 두 단계로 줄임
		RED_HIGHLIGHT=$'\033[1;31m' RED_BRIGHT=$'\033[1;31m'
		RED_MID=$'\033[0;31m' RED_DEEP=$'\033[0;31m' RED_SHADOW=$'\033[0;31m'
		CYAN=$'\033[0;36m' YELLOW=$'\033[1;33m'
	fi
	DIM=$'\033[2m'     # 괄호 안 설명
	BOLD=$'\033[1m'
	REV=$'\033[7m'     # 메뉴 선택 줄
	RESET=$'\033[0m'
else
	TTY=0 ANIM=0
	RED_HIGHLIGHT="" RED_BRIGHT="" RED_MID="" RED_DEEP="" RED_SHADOW="" CYAN="" YELLOW=""
	DIM="" BOLD="" REV="" RESET=""
fi

# 창 크기는 stty 로 읽음. $(tput cols) 는 출력이 파이프라 기본값 80 을 돌려주는 경우가 있음
ROWS="" COLS=""
[ -t 0 ] && read -r ROWS COLS <<<"$(stty size 2>/dev/null)"
[ -n "$COLS" ] || COLS=${COLUMNS:-80}
[ -n "$ROWS" ] || ROWS=${LINES:-24}
case "$COLS" in ''|*[!0-9]*) COLS=80 ;; esac
case "$ROWS" in ''|*[!0-9]*) ROWS=24 ;; esac
# 애니메이션 무대는 100열 × 22줄임. 그보다 작으면 건너뜀
{ [ "$COLS" -lt 100 ] || [ "$ROWS" -lt 24 ]; } && ANIM=0

# 끝날 때 커서·색·키 입력 모드를 되돌림 (Ctrl-C 포함)
STTY_SAVED=""
restore_terminal() {
	[ -n "$STTY_SAVED" ] && stty "$STTY_SAVED" 2>/dev/null
	STTY_SAVED=""
	[ "$TTY" = 1 ] && printf '\033[?25h%s' "$RESET"
}
trap restore_terminal EXIT
trap 'restore_terminal; echo; exit 130' INT TERM

# 배너 글자 부분 (tazo 원본 그대로, 오른쪽 기지국만 떼어 냄)
BANNER_LETTERS=(
	"${RED_SHADOW}  ${RED_HIGHLIGHT}██████${RED_SHADOW}╗  ${RED_HIGHLIGHT}██████${RED_SHADOW}╗ ${RED_HIGHLIGHT}██████${RED_SHADOW}╗ ${RED_HIGHLIGHT}████████${RED_SHADOW}╗${RED_HIGHLIGHT}██████${RED_SHADOW}╗  ${RED_HIGHLIGHT}█████${RED_SHADOW}╗ ${RED_HIGHLIGHT}███${RED_SHADOW}╗   ${RED_HIGHLIGHT}██${RED_SHADOW}╗         ${RED_MID}(("
	"${RED_SHADOW}  ${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗${RED_BRIGHT}██${RED_SHADOW}╔═══${RED_BRIGHT}██${RED_SHADOW}╗${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗╚══${RED_BRIGHT}██${RED_SHADOW}╔══╝${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗${RED_BRIGHT}████${RED_SHADOW}╗  ${RED_BRIGHT}██${RED_SHADOW}║         ${RED_MID}  "
	"${RED_SHADOW}  ${RED_BRIGHT}██████${RED_SHADOW}╔╝${RED_BRIGHT}██${RED_SHADOW}║   ${RED_BRIGHT}██${RED_SHADOW}║${RED_BRIGHT}██████${RED_SHADOW}╔╝   ${RED_BRIGHT}██${RED_SHADOW}║   ${RED_BRIGHT}██████${RED_SHADOW}╔╝${RED_BRIGHT}███████${RED_SHADOW}║${RED_BRIGHT}██${RED_SHADOW}╔${RED_BRIGHT}██${RED_SHADOW}╗ ${RED_BRIGHT}██${RED_SHADOW}║         ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_MID}██${RED_SHADOW}╔═══╝ ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}╗   ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}╗${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}║${RED_MID}██${RED_SHADOW}║╚${RED_MID}██${RED_SHADOW}╗${RED_MID}██${RED_SHADOW}║         ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_MID}██${RED_SHADOW}║     ╚${RED_MID}██████${RED_SHADOW}╔╝${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║${RED_MID}██${RED_SHADOW}║ ╚${RED_MID}████${RED_SHADOW}║         ${RED_DEEP}  "
	"${RED_SHADOW}  ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝         ${RED_DEEP}  "
	"${RED_SHADOW}                                                                       ${RED_DEEP}  "
	"${RED_SHADOW}   ${RED_HIGHLIGHT}█████${RED_SHADOW}╗ ${RED_HIGHLIGHT}████████${RED_SHADOW}╗${RED_HIGHLIGHT}████████${RED_SHADOW}╗ ${RED_HIGHLIGHT}█████${RED_SHADOW}╗  ${RED_HIGHLIGHT}██████${RED_SHADOW}╗${RED_HIGHLIGHT}██${RED_SHADOW}╗  ${RED_HIGHLIGHT}██${RED_SHADOW}╗${RED_HIGHLIGHT}███████${RED_SHADOW}╗${RED_HIGHLIGHT}██████${RED_SHADOW}╗    ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗╚══${RED_BRIGHT}██${RED_SHADOW}╔══╝╚══${RED_BRIGHT}██${RED_SHADOW}╔══╝${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗${RED_BRIGHT}██${RED_SHADOW}╔════╝${RED_BRIGHT}██${RED_SHADOW}║ ${RED_BRIGHT}██${RED_SHADOW}╔╝${RED_BRIGHT}██${RED_SHADOW}╔════╝${RED_BRIGHT}██${RED_SHADOW}╔══${RED_BRIGHT}██${RED_SHADOW}╗   ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_BRIGHT}███████${RED_SHADOW}║   ${RED_BRIGHT}██${RED_SHADOW}║      ${RED_BRIGHT}██${RED_SHADOW}║   ${RED_BRIGHT}███████${RED_SHADOW}║${RED_BRIGHT}██${RED_SHADOW}║     ${RED_BRIGHT}█████${RED_SHADOW}╔╝ ${RED_BRIGHT}█████${RED_SHADOW}╗  ${RED_BRIGHT}██████${RED_SHADOW}╔╝   ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║      ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}║${RED_MID}██${RED_SHADOW}║     ${RED_MID}██${RED_SHADOW}╔═${RED_MID}██${RED_SHADOW}╗ ${RED_MID}██${RED_SHADOW}╔══╝  ${RED_MID}██${RED_SHADOW}╔══${RED_MID}██${RED_SHADOW}╗   ${RED_DEEP}  "
	"${RED_SHADOW}  ${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║      ${RED_MID}██${RED_SHADOW}║   ${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║╚${RED_MID}██████${RED_SHADOW}╗${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}╗${RED_MID}███████${RED_SHADOW}╗${RED_MID}██${RED_SHADOW}║  ${RED_MID}██${RED_SHADOW}║   ${RED_DEEP}  "
	"${RED_SHADOW}  ╚═╝  ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ${RED_DEEP}  "
	"${RED_SHADOW}                                                                       ${RED_HIGHLIGHT}  "
)
# 기지국 부분. 위 글자 줄과 같은 줄 번호로 오른쪽에 붙임
BANNER_TOWER=(
	"${RED_MID}((   ((   ${RED_HIGHLIGHT}▲   ${RED_MID}))   ))"
	"${RED_MID}  ((   (( ║ ))   ))"
	"${RED_DEEP}     ${RED_BRIGHT}▐█▌  ${RED_DEEP}║  ${RED_BRIGHT}▐█▌"
	"${RED_DEEP}     ${RED_BRIGHT}▐█▌${RED_DEEP}══╬══${RED_BRIGHT}▐█▌"
	"${RED_DEEP}     ${RED_BRIGHT}▐█▌  ${RED_DEEP}║  ${RED_BRIGHT}▐█▌"
	"${RED_DEEP}         ╔╩╗"
	"${RED_DEEP}         ╠═╣"
	"${RED_DEEP}        ╔╝ ╚╗"
	"${RED_DEEP}        ╠═══╣"
	"${RED_DEEP}       ╔╝   ╚╗"
	"${RED_DEEP}       ╠═════╣"
	"${RED_DEEP}      ╔╝     ╚╗"
	"${RED_DEEP}  ════╩═══════╩════"
	"${RED_HIGHLIGHT}         gNB"
)

# ── 화면 머리 ────────────────────────────────────────────────────────────

print_banner() {
	local i
	echo
	for i in "${!BANNER_LETTERS[@]}"; do
		# 100열 미만이면 기지국 그림을 빼고 글자만 찍음
		if [ "$COLS" -ge 100 ]; then
			printf '%s\n' "${BANNER_LETTERS[$i]}${BANNER_TOWER[$i]}${RESET}"
		else
			printf '%s\n' "${BANNER_LETTERS[$i]}${RESET}"
		fi
	done
	echo
	printf '  %sv1.0%s     5G 기지국 공격 재현 도구\n' "$BOLD" "$RESET"
	echo
}

# 메뉴마다 화면을 지우고 머리를 다시 찍음. 줄이 모자라면 배너 대신 한 줄 로고만 씀
#   터미널이 아닐 때는 지우지 않고 그대로 이어 찍음
header() {
	[ "$TTY" = 1 ] || return 0
	printf '\033[H\033[2J'
	if [ "$ROWS" -ge 36 ] && [ "$COLS" -ge 75 ]; then
		print_banner
	else
		printf '\n  %s▌PORTRAN ATTACKER▐%s  %s5G 기지국 공격 재현 도구 v1.0%s\n\n' "$RED_BRIGHT$BOLD" "$RESET" "$DIM" "$RESET"
	fi
	[ "$DRY_RUN" = 1 ] && printf '  %s[--dry-run] run·campaign 은 생성 명령만 출력함%s\n' "$YELLOW" "$RESET"
	[ -n "$CRUMB" ] && printf '  %s%s%s\n\n' "$DIM" "$CRUMB" "$RESET"
	return 0
}

# ── 입력 ─────────────────────────────────────────────────────────────────

# choose 제목 항목... : 고른 항목 번호(0부터)를 CHOICE 에 넣음. b 면 1 을 돌려줌
#   DETAILS 배열이 있으면 터미널 화면에서 고른 줄 아래에 설명을 보여 줌
#   입력이 끊기면(EOF) 같은 프롬프트를 끝없이 다시 찍게 되므로 바로 나감
choose() {
	local title=$1 n i key rest sel=0
	shift
	n=$#
	if [ "$TTY" = 0 ]; then
		while true; do
			echo
			echo "$title"
			i=1
			for item in "$@"; do printf '  [%d] %s\n' "$i" "$item"; i=$((i + 1)); done
			printf '  번호, b(뒤로), q(나감) > '
			IFS= read -r key || { echo; exit 1; }
			case "$key" in
			q|Q) exit 0 ;;
			b|B) return 1 ;;
			[1-9]) if [ "$key" -le "$n" ]; then CHOICE=$((key - 1)); return 0; fi ;;
			esac
			echo "  1~$n, b, q 중 하나를 입력할 것"
		done
	fi
	printf '\033[?25l'
	while true; do
		header
		printf '  %s%s%s\n\n' "$BOLD" "$title" "$RESET"
		i=0
		for item in "$@"; do
			if [ "$i" = "$sel" ]; then
				printf '  %s ▶ %d  %s %s\n' "$RED_BRIGHT$REV" "$((i + 1))" "$item" "$RESET"
			else
				printf '     %s%d%s  %s\n' "$RED_MID" "$((i + 1))" "$RESET" "$item"
			fi
			i=$((i + 1))
		done
		[ -n "${DETAILS[$sel]:-}" ] && printf '\n  %s%s%s\n' "$DIM" "${DETAILS[$sel]}" "$RESET"
		printf '\n  %s↑/↓ 또는 숫자 · Enter 선택 · b 뒤로 · q 나감%s' "$DIM" "$RESET"
		IFS= read -rsn1 key || { echo; exit 1; }
		case "$key" in
		$'\033')
			# 화살표는 ESC [ A/B 세 바이트로 옴
			IFS= read -rsn2 rest || rest=""
			case "$rest" in
			'[A') sel=$(((sel + n - 1) % n)) ;;
			'[B') sel=$(((sel + 1) % n)) ;;
			esac ;;
		k|K) sel=$(((sel + n - 1) % n)) ;;
		j|J) sel=$(((sel + 1) % n)) ;;
		'') CHOICE=$sel; printf '\033[?25h\n'; return 0 ;;
		[1-9]) if [ "$key" -le "$n" ]; then CHOICE=$((key - 1)); printf '\033[?25h\n'; return 0; fi ;;
		b|B) printf '\033[?25h\n'; return 1 ;;
		q|Q) printf '\n'; exit 0 ;;
		esac
	done
}

pause() {
	printf '\n  %sEnter 를 누르면 메뉴로 돌아감%s ' "$DIM" "$RESET"
	IFS= read -r _ || { echo; exit 1; }
}

# ── 공격 목록 ─────────────────────────────────────────────────────────────

# same-cell 대상 L3 7종. 순서와 ID 는 ctl.sh same-cell campaign 의 attacks 배열과 같음
SAME_CELL_IDS=(rrc-storm auth-timeout blind-dos uplink-credential-flood downlink-imsi ue-capability l3-06)

# 메뉴 옆 한 줄 설명. 공식 이름·유형·룰은 reproctl.py catalog 에서 읽음
short_desc() {
	case "$1" in
	rrc-storm) echo "Msg4 뒤 RRCSetupComplete 미전송, RRC 컨텍스트 누적" ;;
	auth-timeout) echo "가입자 10명이 Authentication Response 미전송" ;;
	blind-dos) echo "피해자의 현재 5G-GUTI 재사용, 기존 컨텍스트 교란" ;;
	uplink-credential-flood) echo "10초 안 무효·위조 자격증명 등록 실패 10회" ;;
	downlink-imsi) echo "인증 대신 Identity Response(SUCI) 식별자 노출" ;;
	ue-capability) echo "보안 전 요청 없는 UECapabilityInformation 주입" ;;
	l3-06) echo "요청 없는 NAS SecurityModeReject, 카운터 어긋남" ;;
	esac
}

level_label() {
	case "$1" in
	protocol) echo "프로토콜 재현" ;;
	protocol-result-emulation) echo "프로토콜 결과 에뮬레이션" ;;
	protocol-observation-emulation) echo "프로토콜 관측 에뮬레이션" ;;
	detector-input-emulation) echo "탐지 입력 에뮬레이션" ;;
	*) echo "$1" ;;
	esac
}

# reproctl.py catalog --json 을 탭 구분 줄(id 룰 이름 active_mode 유형 별칭)로 바꿈
load_catalog() {
	local rows line ctl id rule name mode level aliases found
	rows=$(cd "$ROOT" && python3 tools/reproctl.py catalog --json | python3 -c '
import json, sys
for v in json.load(sys.stdin):
    print("\t".join([v["id"], ",".join(v["rule_ids"]), v["name"], v.get("active_mode", ""),
                     v["reproduction_level"], ",".join(v.get("aliases", []))]))
') || { echo "run.sh: 공격 목록을 읽지 못함 (python3 tools/reproctl.py catalog --json)" >&2; exit 2; }
	A_ID=() A_RULE=() A_NAME=() A_MODE=() A_LEVEL=()
	for ctl in "${SAME_CELL_IDS[@]}"; do
		found=0
		while IFS=$'\t' read -r id rule name mode level aliases; do
			case ",$id,$aliases," in
			*",$ctl,"*)
				A_ID+=("$ctl") A_RULE+=("$rule") A_NAME+=("$name") A_MODE+=("$mode") A_LEVEL+=("$(level_label "$level")")
				found=1
				break ;;
			esac
		done <<<"$rows"
		[ "$found" = 1 ] || { echo "run.sh: catalog 에 $ctl 이 없음" >&2; exit 2; }
	done
}

# ── 공격 애니메이션 ───────────────────────────────────────────────────────
#
#   무대는 22줄 × 100열 격자임. 왼쪽 위 공격 UE, 왼쪽 아래 정상 UE 5대, 오른쪽 gNB 철탑
#
#   put 줄 열 글자 [색]   한 프레임의 그림을 OUT(화면용)과 GRID(텍스트 저장용)에 같이 씀
#   프레임마다 OUT 을 한 번에 찍어 깜빡임을 줄임

STAGE_H=22 STAGE_W=100
FRAMES=26          # 프레임 수. 0.1초 간격이므로 약 2.6초
TOWER_COL=78       # 철탑 왼쪽 끝 열
LANE_END=77        # 신호가 철탑에 닿는 열
BLANK_LINE=$(printf '%*s' "$STAGE_W" '')

put() {
	local r=$1 c=$2 text=$3 color=${4:-} line cells="" ch i
	# 한글은 화면에서 두 칸이므로 GRID 에는 뒤에 빈 자리 표시(\001)를 하나 더 넣어 열을 맞춤
	for ((i = 0; i < ${#text}; i++)); do
		ch=${text:$i:1}
		case "$ch" in [가-힣]) cells="$cells$ch"$'\001' ;; *) cells="$cells$ch" ;; esac
	done
	line=${GRID[$r]}
	line="${line:0:$c}${cells}${line:$((c + ${#cells}))}"
	GRID[$r]=${line:0:$STAGE_W}
	OUT="$OUT"$'\033['"$((r + 1));$((c + 1))H${color}${text}${RESET}"
}

# 정상 UE 다섯 대의 줄 번호
NORMAL_ROW=(12 14 16 18 20)

draw_scene() {
	local attack=$1 rule=$2 name=$3 r i
	GRID=() OUT=$'\033[H\033[2J'
	for ((r = 0; r < STAGE_H; r++)); do GRID[$r]=$BLANK_LINE; done
	put 0 2 "▶ $rule  $name" "$BOLD$RED_HIGHLIGHT"
	put 1 2 "동작 설명 모션" "$DIM"
	put 1 70 "${SCENE_HINT:-아무 키나 누르면 건너뜀}" "$DIM"
	# 공격 UE
	put 3 2 "┌─────┐" "$RED_BRIGHT"
	put 4 2 "│▚▞▚▞▚│" "$RED_BRIGHT"
	if [ "$TRANSPORT" = usrp ]; then
		put 2 4 "╲│╱" "$YELLOW"
		put 3 2 "┌─┴───┐" "$RED_BRIGHT"
		put 5 2 "│USRP │" "$RED_HIGHLIGHT$BOLD"
	else
		put 5 2 "│ ATK │" "$RED_HIGHLIGHT$BOLD"
	fi
	put 6 2 "└──┬──┘" "$RED_BRIGHT"
	put 7 1 "공격 UE" "$RED_MID"
	if [ "$TRANSPORT" = usrp ]; then
		put 1 2 "USRP ↔ gNB · 차폐 RF 모션" "$YELLOW"
		put 9 2 "TX" "$RED_HIGHLIGHT"
		put 10 2 "RX" "$CYAN"
		put 11 2 "정상 UE 5대 (같은 셀)" "$CYAN"
	else
		put 9 2 "UE ↔ ZMQ broker ↔ gNB" "$DIM"
		put 10 2 "정상 UE 5대 (같은 셀)" "$CYAN"
	fi
	# 정상 UE 5대. 연결선은 철탑 아래까지 이어짐
	for i in 0 1 2 3 4; do
		put "${NORMAL_ROW[$i]}" 2 "[UE$((i + 1))●]" "$CYAN"
		put "${NORMAL_ROW[$i]}" 10 "· · · · · · · · · · · · · · · · · · · · · · · · · · ·" "$DIM"
	done
	# gNB 철탑. 배너의 기지국 그림을 색만 바꿔 다시 씀
	put 2 "$TOWER_COL" "((   ((   ▲   ))   ))" "$RED_MID"
	put 3 "$TOWER_COL" "  ((   (( ║ ))   ))" "$RED_MID"
	put 4 "$TOWER_COL" "     ▐█▌  ║  ▐█▌" "$RED_BRIGHT"
	put 5 "$TOWER_COL" "     ▐█▌══╬══▐█▌" "$RED_BRIGHT"
	put 6 "$TOWER_COL" "     ▐█▌  ║  ▐█▌" "$RED_BRIGHT"
	put 7 "$TOWER_COL" "         ╔╩╗" "$RED_DEEP"
	put 8 "$TOWER_COL" "         ╠═╣" "$RED_DEEP"
	put 9 "$TOWER_COL" "        ╔╝ ╚╗" "$RED_DEEP"
	put 10 "$TOWER_COL" "        ╠═══╣" "$RED_DEEP"
	put 11 "$TOWER_COL" "       ╔╝   ╚╗" "$RED_DEEP"
	put 12 "$TOWER_COL" "       ╠═════╣" "$RED_DEEP"
	put 13 "$TOWER_COL" "      ╔╝     ╚╗" "$RED_DEEP"
	put 14 "$TOWER_COL" "  ════╩═══════╩════" "$RED_DEEP"
	put 15 "$TOWER_COL" "     gNB (CU/DU)" "$RED_HIGHLIGHT"
}

# lane 줄 t 글자 [색] [속도] : 공격 UE 쪽에서 철탑으로 날아가는 신호 하나를 t 시점 위치에 그림
fly() {
	local r=$1 t=$2 text=$3 color=${4:-$RED_BRIGHT} speed=${5:-4} x
	x=$((10 + t * speed))
	[ "$x" -le $((LANE_END - ${#text})) ] || return 1
	put "$r" "$x" "$text" "$color"
}

usrp_exchange() {
	local t=$1 step tx_col rx_col
	step=$((t % 12))
	tx_col=$((12 + step * 5))
	rx_col=$((66 - step * 5))
	put 9 "$tx_col" "))▸" "$RED_HIGHLIGHT"
	put 10 "$rx_col" "◂((" "$CYAN"
}

# 정상 UE 줄의 오른쪽 끝 상태 표시
ue_state() {
	put "${NORMAL_ROW[$1]}" 64 "$2" "${3:-$CYAN}"
}

# 공격별 프레임. 무대 위에 움직이는 부분만 더 그림
frame_rrc_storm() {
	local t=$1 k r x ctx
	# 여러 줄로 RRC 요청이 파도처럼 몰려옴
	for r in 2 3 4 5 6 7 8; do
		for k in 0 1 2; do
			x=$((10 + ((t * 5 + k * 22 + r * 7) % 62)))
			put "$r" "$x" "RRC▸" "$RED_BRIGHT"
		done
	done
	ctx=$((t * 4 > 96 ? 96 : t * 4))
	put 17 79 "RRC 컨텍스트 $(printf '%2d' "$ctx")/96" "$YELLOW$BOLD"
	put 18 79 "Setup Complete 없음" "$RED_MID"
}

frame_auth_timeout() {
	local t=$1 k n
	# 등록 요청은 가고, 인증 요청은 돌아오지만 응답이 안 감
	fly 4 $((t % 9)) "Registration▸" "$RED_BRIGHT" 6 || true
	put 6 $((LANE_END - 13 - (t % 9) * 6 > 10 ? LANE_END - 13 - (t % 9) * 6 : 10)) "◂AuthRequest" "$YELLOW"
	put 8 10 "응답 없음 … … … ◴" "$DIM"
	# 미인증 컨텍스트가 철탑 아래에 쌓임
	n=$((t / 3 + 1)); [ "$n" -gt 10 ] && n=10
	for ((k = 0; k < n; k++)); do
		put $((17 + k / 5)) $((79 + (k % 5) * 4)) "[◴]" "$YELLOW"
	done
	put 16 79 "미인증 컨텍스트 $(printf '%2d' "$n")/10" "$YELLOW$BOLD"
}

frame_blind_dos() {
	local t=$1 i
	put 17 79 "UE 슬롯" "$DIM"
	for i in 0 1 2 3 4; do
		if [ "$i" = 2 ] && [ "$t" -ge 14 ]; then
			put 18 $((79 + i * 4)) "[G]" "$RED_HIGHLIGHT$REV"
		else
			put 18 $((79 + i * 4)) "[$((i + 1))]" "$CYAN"
		fi
	done
	if [ "$t" -lt 14 ]; then
		fly 5 "$t" "위조 GUTI(UE3)▸" "$RED_HIGHLIGHT$BOLD" 5 || true
		ue_state 2 "연결됨" "$CYAN"
	else
		put 5 60 "GUTI 재사용!" "$RED_HIGHLIGHT$BOLD"
		put "${NORMAL_ROW[2]}" 10 "  ✕ ✕ ✕   기존 컨텍스트가 밀려남                      " "$RED_BRIGHT"
		ue_state 2 "끊김" "$RED_HIGHLIGHT$BOLD"
	fi
}

frame_uplink_credential_flood() {
	local t=$1 k x n
	# 가짜 자격증명 폭탄이 연달아 날아가 철탑 앞에서 터짐
	for k in 0 1 2; do
		x=$((10 + ((t * 6 + k * 21) % 63)))
		if [ "$x" -ge 64 ]; then
			put $((3 + k * 2)) 66 "✸ Reject" "$YELLOW$BOLD"
		else
			put $((3 + k * 2)) "$x" "[FAKE-ID]●" "$RED_BRIGHT"
		fi
	done
	n=$((t * 10 / (FRAMES - 4))); [ "$n" -gt 10 ] && n=10
	put 17 79 "등록 실패 $(printf '%2d' "$n")/10 (10초)" "$YELLOW$BOLD"
}

frame_downlink_imsi() {
	local t=$1 k x
	# 인증 대신 식별자 응답이 새어 나와 왼쪽으로 흘러감
	fly 4 $((t % 7)) "Registration▸" "$RED_BRIGHT" 8 || true
	for k in 0 1 2; do
		x=$((LANE_END - 16 - ((t * 5 + k * 20) % 60)))
		[ "$x" -ge 10 ] && put $((6 + k)) "$x" "◂ID-Response(SUCI)" "$YELLOW"
	done
	put 16 79 "식별자 노출 ·:·:·" "$YELLOW$BOLD"
	[ $((t % 2)) = 0 ] && put 17 84 ":·:" "$YELLOW" || put 17 84 "·:·" "$YELLOW"
}

frame_ue_capability() {
	local t=$1
	if [ "$t" -lt 12 ]; then
		fly 5 "$t" "UECapabilityInfo▸" "$RED_HIGHLIGHT$BOLD" 4 || true
		put 17 79 "AS 보안: 아직 없음 ✕" "$RED_MID"
	else
		put 5 56 "보안 전 주입!" "$RED_HIGHLIGHT$BOLD"
		put 17 79 "AS 보안: 아직 없음 ✕" "$RED_MID"
		fly 7 $((t - 12)) "SecurityModeCommand▸" "$DIM" 5 || put 7 58 "보안 시작 (늦음)" "$DIM"
	fi
	put 18 79 "요청 없는 능력 정보" "$YELLOW"
}

frame_l3_06() {
	local t=$1 ue=17 gnb=17
	if [ "$t" -lt 10 ]; then
		fly 5 "$t" "SecurityModeReject▸" "$RED_HIGHLIGHT$BOLD" 6 || true
	else
		ue=$((17 + (t - 9)))
		put 5 54 "요청 안 한 Reject!" "$RED_HIGHLIGHT$BOLD"
	fi
	put 17 79 "UE  NAS COUNT $(printf '%3d' "$ue")" "$CYAN"
	put 18 79 "gNB NAS COUNT $(printf '%3d' "$gnb")" "$RED_BRIGHT"
	if [ "$ue" != "$gnb" ]; then
		put 19 84 "≠ 어긋남" "$YELLOW$BOLD"
	fi
}

# campaign 이면 맨 아래에 공격 전 30초·후 90초 유지 단계를 보여 줌 (시간은 압축)
phase_bar() {
	local t=$1 campaign=$2 pre="" mid="" post=""
	if [ "$campaign" = 1 ]; then
		if [ "$t" -lt 6 ]; then pre=$REV; elif [ "$t" -lt 20 ]; then mid=$REV; else post=$REV; fi
		put 21 2 "정상 유지 30초" "$CYAN$pre"
		put 21 17 "━━▶" "$DIM"
		put 21 21 "공격 phase" "$RED_BRIGHT$mid"
		put 21 32 "━━▶" "$DIM"
		put 21 36 "정상 유지 90초" "$CYAN$post"
		put 21 51 "× 7종 × 3세트" "$DIM"
	else
		put 21 2 "control 다음 공격 phase · 정상 UE 5대 유지" "$DIM"
	fi
}

# render_frame 공격 t campaign : 한 프레임을 OUT/GRID 에 그림
render_frame() {
	local attack=$1 t=$2 campaign=$3 idx i fn
	for i in "${!A_ID[@]}"; do [ "${A_ID[$i]}" = "$attack" ] && idx=$i; done
	draw_scene "$attack" "${A_RULE[$idx]}" "${A_NAME[$idx]}"
	# campaign 은 공격 phase 에서만 신호를 날림
	if [ "$campaign" = 1 ] && { [ "$t" -lt 6 ] || [ "$t" -ge 20 ]; }; then
		if [ "$t" -lt 6 ]; then
			for i in 0 1 2 3 4; do ue_state "$i" "연결됨" "$CYAN"; done
		else
			for i in 0 1 2 3 4; do ue_state "$i" "상태 봉인" "$CYAN"; done
		fi
	else
		fn=frame_$(echo "$attack" | tr '-' '_')
		"$fn" $((campaign == 1 ? (t - 6) * FRAMES / 14 : t))
	fi
	if [ "$TRANSPORT" = usrp ]; then
		usrp_exchange "$t"
		put 21 2 "USRP ↔ gNB 동작 설명 · OTA 실행 adapter 준비 중" "$DIM"
	else
		phase_bar "$t" "$campaign"
	fi
}

# play_animation 공격 campaign : 실행 전 인트로. 키를 누르면 바로 끝남
play_animation() {
	local attack=$1 campaign=$2 t key
	[ "$ANIM" = 1 ] || return 0
	STTY_SAVED=$(stty -g 2>/dev/null)
	stty -icanon -echo min 0 time 0 2>/dev/null
	printf '\033[?25l'
	for ((t = 0; t < FRAMES; t++)); do
		render_frame "$attack" "$t" "$campaign"
		printf '%s' "$OUT"
		sleep 0.1
		key=$(dd bs=1 count=1 2>/dev/null)
		[ -n "$key" ] && break
	done
	restore_terminal
	printf '\033[H\033[2J'
}

# --frames: 프레임 몇 장을 색 없이 텍스트로 저장함
dump_frames() {
	local dir=$1 attack t file campaign transport
	mkdir -p "$dir" || exit 2
	RED_HIGHLIGHT="" RED_BRIGHT="" RED_MID="" RED_DEEP="" RED_SHADOW="" CYAN="" YELLOW=""
	DIM="" BOLD="" REV="" RESET=""
	for transport in zmq usrp; do
		TRANSPORT=$transport
		for attack in "${A_ID[@]}"; do
			file="$dir/frames-$attack.txt"
			[ "$transport" = zmq ] || file="$dir/frames-usrp-$attack.txt"
			: >"$file" || exit 2
			for campaign in 0 1; do
				[ "$transport" = usrp ] && [ "$campaign" = 1 ] && continue
				for t in 2 8 14 20 25; do
					render_frame "$attack" "$t" "$campaign"
					{
						if [ "$transport" = usrp ]; then
							printf -- '── USRP ↔ gNB 모션 · frame %d/%d ──\n' "$((t + 1))" "$FRAMES"
						elif [ "$campaign" = 1 ]; then
							printf -- '── campaign l3-live · frame %d/%d ──\n' "$((t + 1))" "$FRAMES"
						else
							printf -- '── same-cell run · frame %d/%d ──\n' "$((t + 1))" "$FRAMES"
						fi
						printf '%s\n' "${GRID[@]}" | tr -d '\001' | sed 's/[[:space:]]*$//'
						echo
					} >>"$file"
				done
			done
			echo "$file"
		done
	done
}

# ── 실행 ─────────────────────────────────────────────────────────────────

# run_ctl 인자... : ./tools/ctl.sh 공식 명령을 그대로 실행함. 출력은 가리지 않고 흘려보냄
run_ctl() {
	local profile=$1 rc=0 live=0
	shift
	[ "$DRY_RUN" = 1 ] && case " $* " in *" run "*|*" campaign "*) set -- "$@" --dry-run ;; esac
	if [ -n "$LIVE_ATTACK" ]; then
		if live_ok; then live=1; else play_animation "$LIVE_ATTACK" "$LIVE_CAMPAIGN"; fi
	fi
	[ "$live" = 1 ] || ctl_intro "$@"
	if [ "$DRY_RUN" = 1 ] && [ "$2" = doctor ]; then
		echo "  (--dry-run: doctor 는 실행하지 않음)"
		pause
		return 0
	fi
	if [ "$live" = 1 ]; then
		run_live "$profile" "$@" || rc=$?
	else
		ctl_exec "$profile" "$@" || rc=$?
	fi
	echo
	if [ "$rc" = 0 ]; then
		printf '  %s끝남 (종료 코드 0)%s\n' "$CYAN" "$RESET"
	else
		printf '  %s실패 (종료 코드 %d)%s\n' "$RED_HIGHLIGHT$BOLD" "$rc" "$RESET"
	fi
	pause
	return 0
}

# ctl_intro 인자... : 실행 전 안내 한두 줄
ctl_intro() {
	echo
	if [ "$DRY_RUN" = 1 ]; then
		printf '  %s실행:%s ./tools/ctl.sh' "$BOLD" "$RESET"
		printf ' %q' "$@"
		printf '\n\n'
	else
		printf '  실행을 시작합니다. Ctrl-C를 누르면 실행을 중단하고 정리합니다.\n\n'
	fi
}

# ctl_exec 프로필 인자... : 이 DU의 설정을 환경에 싣고 ./tools/ctl.sh 를 실행함
ctl_exec() {
	local profile=$1
	shift
	(
		cd "$ROOT" || exit 2
		# dry-run도 이 DU의 실제 설정 경로를 사용한다.
		profile_env=$(python3 tools/reproctl.py env --profile "$profile") || exit 2
		while IFS= read -r line; do export "$line"; done <<<"$profile_env"
		# 출력이 파이프여도 python 로그가 바로 나오게 함
		export PYTHONUNBUFFERED=1
		"$CTL" "$@"
	)
}

# ── 실행 중 모션 ──────────────────────────────────────────────────────────
#   위 STAGE_H 줄은 모션, 그 아래 한 줄은 구분선, 나머지는 ctl.sh 로그 스크롤 영역
#   화면에 쓰는 것은 live_render 하나뿐임. ctl.sh 출력은 FIFO 로 받아 live_render 가 찍음
LIVE_ATTACK="" LIVE_CAMPAIGN=0 LIVE_INT=0
LIVE_MIN_ROWS=$((STAGE_H + 1 + 8))

# shortcut: EPOCHREALTIME·read -t 소수 초가 필요해 bash 5 이상만 실행 중 모션을 씀. 그 아래는 인트로 모션으로 대신함
# shortcut: 실행 중 창 크기 변경은 반영하지 않음. 필요해지면 SIGWINCH 에서 영역을 다시 잡음
live_ok() {
	[ "$ANIM" = 1 ] && [ "$TTY" = 1 ] && [ "${BASH_VERSINFO[0]}" -ge 5 ] && [ "$ROWS" -ge "$LIVE_MIN_ROWS" ]
}

# live_render 작업폴더 : 표준 입력(FIFO)의 로그를 아래 영역에, 0.1초마다 다음 모션 프레임을 위 영역에 그림
live_render() {
	local dir=$1 t=0 line="" part rc now last=0 r clear="" width
	# Ctrl-C 뒤에도 ctl.sh 정리 로그를 끝까지 받아야 하므로 렌더러는 신호를 무시함
	trap '' INT TERM
	SCENE_HINT="실행 중 · Ctrl-C 중단"
	for ((r = 1; r <= STAGE_H; r++)); do clear="$clear"$'\033['"$r;1H"$'\033[2K'; done
	# tr 은 여러 바이트 글자를 못 다루므로 치환으로 선을 만듦
	width=${BLANK_LINE:12}
	printf '\033[%d;1H%s── 실행 로그 %s%s' "$((STAGE_H + 1))" "$DIM" "${width// /─}" "$RESET"
	while true; do
		now=${EPOCHREALTIME/[.,]/}
		if [ $((now - last)) -ge 100000 ]; then
			render_frame "$LIVE_ATTACK" "$((t % FRAMES))" "$LIVE_CAMPAIGN"
			printf '%s%s' "$clear" "${OUT#$'\033[H\033[2J'}"
			t=$((t + 1)) last=$now
		fi
		part=""
		IFS= read -r -t 0.1 part
		rc=$?
		if [ "$rc" = 0 ]; then
			printf '\033[%d;1H\n%s%s' "$ROWS" "$line$part" "$RESET"
			line=""
		elif [ "$rc" -gt 128 ]; then
			# 시간 초과: 받다 만 줄은 이어 붙임. ctl.sh 가 끝났으면 손자 프로세스가 FIFO 를 잡고 있어도 나감
			line=$line$part
			[ -e "$dir/done" ] && break
		else
			[ -n "$line$part" ] && printf '\033[%d;1H\n%s%s' "$ROWS" "$line$part" "$RESET"
			break
		fi
	done
	[ -n "$line" ] && printf '\033[%d;1H\n%s%s' "$ROWS" "$line" "$RESET"
}

# run_live 프로필 인자... : 화면을 나눠 ctl.sh 를 실행함. 종료 코드는 ctl.sh 의 것을 그대로 돌려줌
run_live() {
	local dir rc=0 render_pid
	dir=$(mktemp -d "${TMPDIR:-/tmp}/run-live.XXXXXX") || return 2
	mkfifo "$dir/log" || { rm -rf "$dir"; return 2; }
	# Ctrl-C 는 ctl.sh 가 받아 정리함. 여기서는 표시만 해 두고 정리 로그를 끝까지 보여 준 뒤 나감
	LIVE_INT=0
	trap 'LIVE_INT=1' INT TERM
	STTY_SAVED=$(stty -g 2>/dev/null)
	stty -echo 2>/dev/null
	printf '\033[?25l\033[H\033[2J\033[%d;%dr' "$((STAGE_H + 2))" "$ROWS"
	live_render "$dir" <"$dir/log" &
	render_pid=$!
	# 안내 줄도 로그 영역에 찍히도록 같은 FIFO 로 보냄
	{ ctl_intro "${@:2}"; ctl_exec "$@"; } >"$dir/log" 2>&1 || rc=$?
	: >"$dir/done"
	# 신호가 오면 wait 가 일찍 끝나므로 렌더러가 실제로 끝날 때까지 기다림
	while kill -0 "$render_pid" 2>/dev/null; do wait "$render_pid" 2>/dev/null; done
	printf '\033[r\033[%d;1H' "$ROWS"
	restore_terminal
	rm -rf "$dir"
	trap 'restore_terminal; echo; exit 130' INT TERM
	[ "$LIVE_INT" = 1 ] && { echo; exit 130; }
	return "$rc"
}

# 캠페인 ID는 접두어 l3를 포함해 최대 24자. 같은 초의 연속 실행도 구분한다.
automatic_id() { printf '%s-%s-%04x' "$1" "$(date -u +%Y%m%dT%H%M%SZ)" "$RANDOM"; }

# 공격 하나에 대한 작업 메뉴
action_menu() {
	local profile=$1 idx=$2 attack mode label run_id campaign_id
	attack=${A_ID[$idx]} mode=${A_MODE[$idx]}
	label="${A_RULE[$idx]} ${A_NAME[$idx]}"
	while true; do
		CRUMB="DU 설정 $profile › $label (${A_LEVEL[$idx]})"
		DETAILS=(
			"./tools/ctl.sh same-cell doctor --profile $profile"
			"./tools/ctl.sh same-cell run $attack --profile $profile --mode control"
			"./tools/ctl.sh same-cell run $attack --profile $profile --mode $mode --enable"
			"./tools/ctl.sh same-cell campaign l3-live --profile $profile --sets 3 --count 5 --enable  (L3 7종 전체)"
		)
		choose "작업 선택" \
			"same-cell doctor     정상 UE 5대·L3 7종 실행 준비 점검" \
			"same-cell run        control (정상 대조 실행)" \
			"same-cell run        $mode (공격 phase 실행)" \
			"same-cell campaign   l3-live 7종 × control→active 3세트" || return 0
		DETAILS=()
		case "$CHOICE" in
		0) run_ctl "$profile" same-cell doctor --profile "$profile" ;;
		1)
			run_id=$(automatic_id "sc-$attack-control")
			run_ctl "$profile" same-cell run "$attack" --profile "$profile" --mode control --run-id "$run_id" ;;
		2)
			run_id=$(automatic_id "sc-$attack-$mode")
			LIVE_ATTACK=$attack LIVE_CAMPAIGN=0
			run_ctl "$profile" same-cell run "$attack" --profile "$profile" --mode "$mode" --run-id "$run_id" --enable
			LIVE_ATTACK="" ;;
		3)
			campaign_id=$(automatic_id l3)
			LIVE_ATTACK=$attack LIVE_CAMPAIGN=1
			run_ctl "$profile" same-cell campaign l3-live --profile "$profile" --campaign-id "$campaign_id" --sets 3 --count 5 --enable
			LIVE_ATTACK="" ;;
		esac
	done
}

attack_menu() {
	local profile=$1 i
	local -a items
	while true; do
		CRUMB="환경 $ENV_LABEL"
		[ "$TRANSPORT" = usrp ] || CRUMB="$CRUMB › DU 설정 $profile"
		items=() DETAILS=()
		for i in "${!A_ID[@]}"; do
			items+=("$(printf '%-8s %-24s %s' "${A_RULE[$i]}" "${A_ID[$i]}" "$(short_desc "${A_ID[$i]}")")")
			DETAILS+=("${A_NAME[$i]} · ${A_LEVEL[$i]} · active=${A_MODE[$i]}")
		done
		local title="공격 선택 (L3 7종, 정상 UE 5대와 같은 셀)"
		[ "$TRANSPORT" = zmq ] || title="USRP ↔ gNB 공격 모션 선택 (OTA 실행 adapter 준비 중)"
		choose "$title" "${items[@]}" || { DETAILS=(); return 0; }
		DETAILS=()
		if [ "$TRANSPORT" = usrp ]; then
			if [ "$ANIM" = 1 ]; then
				play_animation "${A_ID[$CHOICE]}" 0
			else
				render_frame "${A_ID[$CHOICE]}" 14 0
				printf '%s\n' "${GRID[@]}" | tr -d '\001' | sed 's/[[:space:]]*$//'
			fi
			echo "  USRP ↔ gNB 동작 모션입니다. OTA 실행 adapter는 준비 중입니다."
			pause
		else
			action_menu "$profile" "$CHOICE"
		fi
	done
}

main_menu() {
	local profile
	while true; do
		CRUMB=""
		DETAILS=("이 DU의 설정을 자동으로 읽어 정상 UE 5대와 실행" "USRP와 gNB 사이의 공격 동작 모션 · OTA 실행 adapter 준비 중")
		choose "환경 설정" \
			"가상    (ZMQ, 송신 없음)" \
			"실장비  (USRP ↔ gNB 모션)" || continue
		DETAILS=()
		case "$CHOICE" in
		0)
			ENV_LABEL="가상(ZMQ)"; TRANSPORT=zmq
			if profile=$(python3 "$ROOT/tools/reproctl.py" local-profile --backend p5); then
				echo "  DU 설정 적용됨 ($profile)"
				attack_menu "$profile"
			else
				pause
			fi ;;
		1)
			ENV_LABEL="실장비(USRP)"; TRANSPORT=usrp
			attack_menu "" ;;
		esac
	done
}

load_catalog
if [ -n "$FRAMES_DIR" ]; then
	dump_frames "$FRAMES_DIR"
	exit 0
fi
CRUMB="" DETAILS=() ENV_LABEL=""
# 터미널이 아니면 배너를 처음에 한 번만 찍음 (메뉴는 이어 찍음)
[ "$TTY" = 1 ] || print_banner
main_menu
