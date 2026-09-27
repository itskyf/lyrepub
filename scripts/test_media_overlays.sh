#!/usr/bin/env bash
set -euo pipefail

fixture_dir=$(mktemp -d)
trap 'rm -rf "$fixture_dir"' EXIT

pixi run ffmpeg -hide_banner -loglevel error \
	-f lavfi -i 'sine=frequency=440:sample_rate=48000:duration=1' \
	-c:a libopus -b:a 16k -map_metadata -1 -y "$fixture_dir/tone.opus"
LYREPUB_TEST_OPUS="$fixture_dir/tone.opus" \
	pixi run --environment dev python -m pytest "$@"
