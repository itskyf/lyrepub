#!/usr/bin/env bash
set -o errexit -o nounset

usage() {
	cat <<EOF
Usage: ${0##*/} [--help]

Download the original research sources into data/bronze/.
The script can be run from any working directory.
EOF
}

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
*)
	printf 'Usage: %s [--help]\n' "${0##*/}" >&2
	exit 2
	;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

BRONZE_DIR="${REPO_ROOT}/data/bronze"
DEM_HOI_DIR="${BRONZE_DIR}/9786326186253"
THANG_LONG_NOI_GIAN_DIR="${BRONZE_DIR}/9786045633946"

mkdir --parents "$DEM_HOI_DIR" "$THANG_LONG_NOI_GIAN_DIR"

CURL_ARGS=(
	--fail
	--location
	--remote-name
	--remote-header-name
	--remove-on-error
)

# https://dtv-ebook.com.vn/dem-hoi-long-tri_6504.html
printf '\nIngesting: Đêm hội Long Trì — EPUB\n' >&2

curl "${CURL_ARGS[@]}" \
	--output-dir "$DEM_HOI_DIR" \
	"https://docs.google.com/uc?id=0B3fq_8MMSN0Ya0J6RE9NalJCbW8"

DEM_HOI_AUDIO_URLS=(
	"https://archive.org/download/dem-hoi-5/dem-hoi-1.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-2.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-3.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-4.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-5.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-6.mp3"
	"https://archive.org/download/dem-hoi-5/dem-hoi-7.mp3"
)

for i in "${!DEM_HOI_AUDIO_URLS[@]}"; do
	chapter=$((i + 1))

	printf '\nIngesting: Đêm hội Long Trì — audiobook track %d/%d\n' \
		"$chapter" "${#DEM_HOI_AUDIO_URLS[@]}" >&2

	curl "${CURL_ARGS[@]}" \
		--output-dir "$DEM_HOI_DIR" \
		"${DEM_HOI_AUDIO_URLS[$i]}"
done

# https://dtv-ebook.com.vn/ebook-thang-long-noi-gian-hoang-quoc-hai-full-prc-pdf-epub-azw3-tieu-thuyet_3084.html
printf '\nIngesting: Thăng Long nổi giận — EPUB\n' >&2

curl "${CURL_ARGS[@]}" \
	--output-dir "$THANG_LONG_NOI_GIAN_DIR" \
	"https://docs.google.com/uc?id=0B2Ddxco7EoJlLXZoSE9uTFdmTjg"

printf '\nSources ingested: %s\n' "$BRONZE_DIR" >&2
