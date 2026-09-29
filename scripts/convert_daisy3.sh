#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

usage() {
	cat <<EOF
Usage: ${0##*/} EPUB [--help]

Convert a validated EPUB 3 publication to the DAISY 3 submission package
required by docs/research/protocol.md section 7, using the DAISY Pipeline
Compose service and the dp2 CLI (epub3-to-daisy3, then daisy3-upgrader with
ensure-core-media). The script can be run from any working directory.

Writes into data/daisy3/<EPUB stem>/:
  <stem>-daisy3.zip             DAISY 3 submission ZIP
  <stem>-daisy3.zip.sha256.txt  SHA-256 hash of the ZIP
EOF
}

case "$#" in
1)
	if [[ "$1" == "--help" ]]; then
		usage
		exit 0
	fi
	;;
*)
	usage >&2
	exit 2
	;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

EPUB_NAME="$(basename -- "$1")"
EPUB_PATH="$(cd -- "$(dirname -- "$1")" && pwd)/${EPUB_NAME}"
STEM="${EPUB_NAME%.*}"
OUT_DIR="${REPO_ROOT}/data/daisy3/${STEM}"
WORK_DIR="$(mktemp --directory)"
trap 'rm --recursive --force -- "${WORK_DIR}"' EXIT

mkdir --parents "$OUT_DIR"

podman compose --file "${REPO_ROOT}/compose.yaml" up --detach --wait daisy-pipeline

python3 - "$EPUB_PATH" "${WORK_DIR}/context.zip" <<'PY'
import os
import sys
import zipfile

source, target = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(target, "w") as archive:
	archive.write(source, os.path.basename(source))
PY

dp2 --host http://127.0.0.1 --port 8181 epub3-to-daisy3 \
	--data "${WORK_DIR}/context.zip" \
	--source "$EPUB_NAME" \
	--output "${WORK_DIR}/daisy3.zip" \
	--zip

# The DAISY 3 package file produced by epub3-to-daisy3 is always result/book.opf.
dp2 --host http://127.0.0.1 --port 8181 daisy3-upgrader \
	--data "${WORK_DIR}/daisy3.zip" \
	--source result/book.opf \
	--ensure-core-media true \
	--output "${WORK_DIR}/upgraded.zip" \
	--zip

# Strip Pipeline's result/ envelope so the ZIP root is the DAISY 3 package.
python3 - "${WORK_DIR}/upgraded.zip" "${OUT_DIR}/${STEM}-daisy3.zip" <<'PY'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as source, zipfile.ZipFile(sys.argv[2], "w") as target:
	for name in source.namelist():
		if name != "result/":
			target.writestr(name.removeprefix("result/"), source.read(name))
PY

(
	cd -- "$OUT_DIR"
	sha256sum -- "${STEM}-daisy3.zip" >"${STEM}-daisy3.zip.sha256.txt"
)

printf 'DAISY 3 submission written to %s\n' "$OUT_DIR" >&2
