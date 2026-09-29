# Final publication reproduction and validation

The work contract and reviewed publication decisions are in
[Issue #17](https://github.com/itskyf/lyrepub/issues/17).
Generated publications, audio, reports, and review material are under
`data/issue-17/`; they are not committed.

## Reproduction

Use fresh output directories. Set `TTS_SOURCE`, `MODEL_GGUF`,
and `VOICE_DIR` to the existing bronze books, pinned VieNeu checkpoint, and
Quỳnh Anh voice directory. The frozen frontend and assets are checked by the
existing Issue #14 functions before synthesis.

```sh
TTS_OUT=data/issue-17/tts
ALIGNMENT_OUT=data/issue-17/alignment

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 pixi run -e dev python -m scripts.issue17_tts \
  prepare --source "$TTS_SOURCE" --output "$TTS_OUT"
pixi run -e dev python -m scripts.issue17_tts synthesize \
  --output "$TTS_OUT" --model "$MODEL_GGUF" --voice "$VOICE_DIR"
pixi run -e dev python -m scripts.issue17_tts publish \
  --source "$TTS_SOURCE" --output "$TTS_OUT"

align process data/bronze/9786326186253 "$ALIGNMENT_OUT/processed-audio" \
  --log-level info
align align --ctc --emissions data/silver/issue-15/emissions \
  --audiobook "$ALIGNMENT_OUT/processed-audio" \
  --epub data/silver/issue-15/markedup.epub --language vi --granularity sentence \
  --reports "$ALIGNMENT_OUT/report.json" \
  --output "$ALIGNMENT_OUT/regenerated.epub" --time --log-level info
pixi run -e dev python -m scripts.issue17_publication \
  --source "$ALIGNMENT_OUT/regenerated.epub" --output "$ALIGNMENT_OUT" \
  --frozen-report data/silver/issue-15/report.json \
  --regenerated-report "$ALIGNMENT_OUT/report.json"
```

The alignment command consumes retained emissions; it does not generate them.
Storyteller 0.2.4 and Node.js 26.10.0 reproduced the frozen report exactly.
The report records spans rather than every sentence timestamp. Verification
checks those span boundaries and the four previously recorded manual timing
boundaries; it does not claim an independent historical reference for every
sentence. All 3,382 regenerated SMIL `par` identities, text references, and
timing strings remained identical through final packaging.

Native audio.cpp request sequences amortize model loading over each TTS spine
document. Every prepared phoneme chunk retains its own frozen block seed and
exact UTF-8 chunk budget. A two-request probe produced byte-identical 48 kHz
stereo PCM to the existing single-request CLI path, including the repeated
request. Request JSON is temporary runtime input, not a second text corpus.
VieNeu/SEA-G2P chunk joining and final Opus duration measurement reuse Issue #14.
FFmpeg/ffprobe 9.0.2 performs the publication Opus encoding and duration checks.
Completed spine documents can be resumed with the same verified runtime.

## Automated checks

```sh
pixi run -e dev python -m pytest -q tests/test_issue17_publication.py \
  tests/test_issue14_feasibility.py tests/test_sentence_targets.py \
  tests/test_media_overlays.py
pixi run -e dev python -m pytest -q
hk check --pr

for pathway in tts alignment; do
  podman run --rm --security-opt label=disable -v "$PWD/data:/data:ro" \
    localhost/lyrepub-epubcheck:5.4.0 \
    "/data/issue-17/$pathway/final.epub"
  podman run --rm --userns=keep-id:uid=10042,gid=999 \
    --security-opt label=disable -v "$PWD/data:/data" \
    localhost/lyrepub-ace:1.4.6 \
    "/data/issue-17/$pathway/final.epub" \
    -o "/data/issue-17/$pathway/ace" --force
done
```

The Ace user mapping uses the image's existing Puppeteer browser and permits
report writes to the host directory. No reader or browser is installed on
the host. The same image can produce focused screenshots from extracted final
XHTML for visual review.

Before and after publication work, SHA-256 checks covered all 280 retained
files under `data/silver/issue-14/`, `data/silver/issue-14-reported/`, and
`data/silver/issue-15/`. The originals remain unchanged.

## Human review material

Alignment review material includes the final EPUB, extracted final XHTML,
author/chapter/note screenshots, source images, reviewed image alternatives,
and 16 kHz mono PCM WAV excerpts decoded from the final Opus tracks.
The excerpts cover source-track intervals 65.9–122.7 and 467.8–529 seconds
on track 1, 0–34 seconds on track 2, 904–950.5 seconds on track 6, and the
spoken-note context at 1075.5–1125.9 seconds on track 2.
These excerpts support final listening; they do not replace alignment inputs
or establish new timing references.

The source's title-attribute notes are exposed as linked footnotes with
backlinks in the final copy. Their exact note text and original sentence IDs
remain available. Image-only back-cover content requires reviewed text
alternatives. Accessibility summaries retain known synchronization limitations
and do not assert completed human review.

The user reviewed the cover/portrait alternatives and confirmed the back-cover
readings "chồng chất" and "oan khiên" against magnified original pixels.
The final image alternative contains the reviewed transcription. This text is
absent from the audiobook; auditory access is not declared sufficient. No audio
was added to the alignment pathway. The repaired alignment EPUB currently has
zero EPUBCheck errors/warnings and no automated Ace findings.

All 118 frozen benchmark sentences retain their source ranges, synthesis inputs,
normalized chunks, phonemes, and clip durations in the full TTS run. Decoded Opus
PCM matches for 117; `s5-b9` sentence 39 differs despite those matching settings.
The diagnostic comparison is retained in `tts/benchmark-preservation.json`, with
both recordings linked in `review.html`. An isolated single request and a
two-request native batch both reproduced the frozen PCM exactly; the full-spine
batch recording differs. Those probes are retained in
`tts/single-request-diagnostic/` and `tts/isolated-batch-diagnostic/`. The cause
of the full-spine difference remains unresolved; byte-identical full-book
synthesis is not claimed.

Full TTS synthesis completed all 3,033 source blocks and 10,343 sentences.
The packaged EPUB preserves every authored body character in all 26 source
documents; its 10,343 unique overlay clips match the measured sentence audio.
The complete TTS EPUB passed EPUBCheck with zero errors and warnings.
Its final Ace run is in progress. Validation logs are retained in
`tts/epubcheck.txt` and `tts/ace.txt`.

The latest focused suite passed 28 tests; the full suite passed 39;
`hk check --pr` passed. `review.html` links both complete EPUBs, decoded alignment
excerpts, TTS spot checks, and visual samples. The TTS screenshots use XHTML
identical to the final publication. The inherited standalone "V" at chapter 1
and "P hú quốc Cường binh sách"/stray "P" at chapter 12 remain unchanged for
content review. Reader synchronization, listening, and final accessibility
review remain pending; no completed human review or conformance is asserted.
