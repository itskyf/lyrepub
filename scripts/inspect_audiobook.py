"""Inspect the Đêm hội Long Trì audiobook tracks (Issue #11).

Summarizes ffprobe metadata (collected by scripts/inspect_audiobook.sh) per
track and per-spine-item extracted character counts, all descriptive. When
tracks have been identified by manual listening, TRACK_SECTION_CORRESPONDENCE
below holds that observed mapping and the report adds chars/s per
track/section set as a descriptive sanity check; evidence lives in
docs/research/source-characterization.md, not in this file. Unconfirmed
tracks stay out of the mapping.

Usage:
    pixi run --environment dev python scripts/inspect_audiobook.py

Reads data/silver/*.ffprobe.json, data/silver/ffprobe_version.txt, and
data/silver/blocks.csv; writes data/silver/audiobook_tracks.csv and
data/silver/audiobook_report.txt.
"""

import csv
import json
import logging
import re
import statistics
from pathlib import Path

logger = logging.getLogger("audiobook")

REPO_ROOT = Path(__file__).resolve().parents[1]
ISBN = "9786326186253"
_STEM = re.compile(r"dem-hoi-(\d+)$")
_SPINE_LABELS = {
    0: "cover",
    1: "author bio, no toc entry",
    2: "LỜI NÓI ĐẦU",
    3: "I",
    4: "II",
    5: "III",
    6: "IV",
    7: "V",
    8: "VI",
    9: "VII",
    10: "closing image page, no toc entry",
}

# Manually observed track -> narrated spine indices; filled only from
# listening evidence recorded in docs/research/source-characterization.md.
TRACK_SECTION_CORRESPONDENCE: dict[int, tuple[int, ...]] = {
    1: (1, 2, 3),
    2: (4,),
    3: (5,),
    4: (6,),
    5: (7,),
    6: (8,),
    7: (9,),
}


def _probe_files(silver: Path) -> dict[int, Path]:
    """Map track numbers to their ffprobe JSON files."""
    files: dict[int, Path] = {}
    for path in sorted(silver.glob("dem-hoi-*.ffprobe.json")):
        match = _STEM.fullmatch(path.name.removesuffix(".ffprobe.json"))
        if match is None:
            msg = f"unrecognized probe file name: {path.name}"
            raise ValueError(msg)
        files[int(match.group(1))] = path
    if not files:
        msg = "no data/silver/dem-hoi-*.ffprobe.json; run scripts/inspect_audiobook.sh"
        raise ValueError(msg)
    return files


def _track_row(track: int, path: Path) -> dict[str, object]:
    probe = json.loads(path.read_text(encoding="utf-8"))
    audio = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "audio"
    )
    tags = probe["format"].get("tags", {})
    return {
        "isbn": ISBN,
        "track": track,
        "file": f"dem-hoi-{track}.mp3",
        "duration_s": float(probe["format"]["duration"]),
        "bit_rate": probe["format"].get("bit_rate", ""),
        "codec": audio["codec_name"],
        "sample_rate": audio.get("sample_rate", ""),
        "channels": audio.get("channels", ""),
        "tags": " ".join(f"{key}={value}" for key, value in sorted(tags.items())),
    }


def _spine_chars() -> dict[int, int]:
    """Sum extracted block character counts per spine index from the scan."""
    blocks_csv = REPO_ROOT / "data/silver/blocks.csv"
    with blocks_csv.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["isbn"] == ISBN]
    chars: dict[int, int] = {}
    for row in rows:
        chars[int(row["spine_index"])] = chars.get(int(row["spine_index"]), 0) + int(
            row["char_len"]
        )
    return chars


def _report_lines(
    version: str,
    tracks: list[dict[str, object]],
    spine_chars: dict[int, int],
) -> list[str]:
    lines = [f"ffprobe: {version}", "", "-- tracks --"]
    lines.extend(
        f"track {row['track']} {row['file']} duration_s={row['duration_s']:.1f} "
        f"bit_rate={row['bit_rate']} codec={row['codec']} "
        f"sample_rate={row['sample_rate']} channels={row['channels']} "
        f"tags={row['tags']}"
        for row in tracks
    )
    total = sum(float(row["duration_s"]) for row in tracks)
    lines.append(f"total duration_s={total:.1f}")

    lines.append("")
    lines.append("-- per-spine-item extracted characters --")
    lines.extend(
        f"s{index} ({_SPINE_LABELS.get(index, '?')}): chars={spine_chars.get(index, 0)}"
        for index in sorted(spine_chars)
    )
    lines.extend(_correspondence_lines(tracks, spine_chars))
    return lines


def _correspondence_lines(
    tracks: list[dict[str, object]], spine_chars: dict[int, int]
) -> list[str]:
    """Descriptive chars/s per listening-confirmed track/section set."""
    if not TRACK_SECTION_CORRESPONDENCE:
        return [
            "",
            "-- track/section correspondence --",
            "not yet established by listening",
        ]
    by_track = {int(row["track"]): row for row in tracks}
    lines = ["", "-- track/section correspondence (manual observation) --"]
    rates: list[float] = []
    for track in sorted(TRACK_SECTION_CORRESPONDENCE):
        sections = TRACK_SECTION_CORRESPONDENCE[track]
        row = by_track.get(track)
        if row is None:
            msg = f"correspondence references unknown track {track}"
            raise ValueError(msg)
        chars = sum(spine_chars.get(index, 0) for index in sections)
        duration = float(row["duration_s"])
        rate = chars / duration
        rates.append(rate)
        labels = ", ".join(f"s{i} ({_SPINE_LABELS.get(i, '?')})" for i in sections)
        lines.append(
            f"track {track}: {labels} chars={chars} duration_s={duration:.1f} "
            f"chars_per_s={rate:.1f}"
        )
    lines.append(
        f"chars_per_s across confirmed tracks: median={statistics.median(rates):.1f} "
        f"min={min(rates):.1f} max={max(rates):.1f} (descriptive only)"
    )
    return lines


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    silver = REPO_ROOT / "data" / "silver"

    version = (silver / "ffprobe_version.txt").read_text(encoding="utf-8").strip()
    probe_files = sorted(_probe_files(silver).items())
    tracks = [_track_row(track, path) for track, path in probe_files]

    tracks_csv = silver / "audiobook_tracks.csv"
    with tracks_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(tracks[0]))
        writer.writeheader()
        writer.writerows(tracks)

    lines = _report_lines(version, tracks, _spine_chars())
    report = silver / "audiobook_report.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        logger.info("%s", line)


if __name__ == "__main__":
    main()
