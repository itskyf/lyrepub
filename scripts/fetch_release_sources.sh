#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

usage() {
	cat <<EOF
Usage: ${0##*/} [--help]

Download and extract bronze research sources from GitHub release v0.3.0 into data/.
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

DATA_DIR="${REPO_ROOT}/data"
BRONZE_DIR="${DATA_DIR}/bronze"
REPO="itskyf/lyrepub"
TAG="v0.3.0"

mkdir --parents "$DATA_DIR"

printf '\nFetching release sources: %s (%s)\n' "$TAG" "bronze.tar.gz" >&2

gh release download "$TAG" \
	--repo "$REPO" \
	--pattern 'bronze.tar.gz' \
	--output - |
	tar --extract --gzip --directory "$REPO_ROOT"

printf '\nSources fetched: %s\n' "$BRONZE_DIR" >&2
