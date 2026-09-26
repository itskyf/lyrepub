#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

usage() {
	cat <<EOF
Usage: ${0##*/} [--help] [excerpts SECONDS]

Probe each Đêm hội Long Trì audiobook track with ffprobe into
data/silver/<track>.ffprobe.json and record the ffprobe version. With
"excerpts SECONDS", also extract the first SECONDS seconds of each track
(stream copy) into data/silver/ for manual listening. The script can be run
from any working directory.
EOF
}

MODE=metadata
EXCERPT_SECONDS=0

case "$#" in
0) ;;
1)
	if [[ "$1" == "--help" ]]; then
		usage
		exit 0
	fi

	printf 'Unknown argument: %s\n' "$1" >&2
	usage >&2
	exit 2
	;;
2)
	if [[ "$1" == "excerpts" && "$2" =~ ^[0-9]+$ && "$2" -gt 0 ]]; then
		MODE=excerpts
		EXCERPT_SECONDS="$2"
	else
		printf 'Invalid arguments: %s %s\n' "$1" "$2" >&2
		usage >&2
		exit 2
	fi
	;;
*)
	printf 'Usage: %s [--help] [excerpts SECONDS]\n' "${0##*/}" >&2
	exit 2
	;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
BRONZE_DIR="${REPO_ROOT}/data/bronze/9786326186253"
SILVER_DIR="${REPO_ROOT}/data/silver"

mkdir --parents "$SILVER_DIR"

ffprobe -version | head -n 1 >"${SILVER_DIR}/ffprobe_version.txt"

for track in 1 2 3 4 5 6 7; do
	stem="dem-hoi-${track}"
	audio="${BRONZE_DIR}/${stem}.mp3"
	probe="${SILVER_DIR}/${stem}.ffprobe.json"
	ffprobe -v error -print_format json -show_format -show_streams "$audio" >"$probe"
	printf 'wrote %s\n' "$probe" >&2

	if [[ "$MODE" == "excerpts" ]]; then
		excerpt="${SILVER_DIR}/excerpt-${stem}-head-${EXCERPT_SECONDS}s.mp3"
		ffmpeg -v error -i "$audio" -t "$EXCERPT_SECONDS" -c copy "$excerpt"
		printf 'wrote %s\n' "$excerpt" >&2
	fi
done
