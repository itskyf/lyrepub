# Final publication reproduction and validation

[Issue #17](https://github.com/itskyf/lyrepub/issues/17) records the publication decisions.
The current #17 sentence records and reusable Opus clips are in `data/silver/issue-17/thang-long-noi-gian/`; benchmark records are in `data/silver/issue-17/tts-benchmark/`, and the regenerated alignment report is in `data/silver/issue-17/dem-hoi-long-tri/report.json`.
The final EPUBs are `data/gold/thang-long-noi-gian.epub` and `data/gold/dem-hoi-long-tri.epub`.
The acquired sources and frozen `data/silver/issue-14/`, `data/silver/issue-14-reported/`, and `data/silver/issue-15/` evidence are unchanged.

## Reproduction

Set `TTS_SOURCE` to the acquired Thăng Long nổi giận EPUB in `data/bronze/`, and use fresh work directories for a new run.
The frozen TTS frontend and audio.cpp inference configuration are those of [#14](tts-feasibility.md); only the publication outputs are new.
Browser validation is optional and separated below; reproducing the EPUBs does not require the Playwright service.

```sh
podman compose up --detach audiocpp
TTS_OUT=data/silver/issue-17/thang-long-noi-gian
TTS_WORK=data/work/issue-17/thang-long-noi-gian
TTS_FINAL=data/gold/thang-long-noi-gian.epub
ALIGNMENT_OUT=data/silver/issue-17/dem-hoi-long-tri
ALIGNMENT_WORK=data/work/issue-17/dem-hoi-long-tri
ALIGNMENT_FINAL=data/gold/dem-hoi-long-tri.epub
BENCHMARK_OUT=data/silver/issue-17/tts-benchmark
BENCHMARK_WORK=data/work/issue-17/tts-benchmark

PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  prepare --source-epub "$TTS_SOURCE" --output "$BENCHMARK_OUT"
PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_benchmark.py synthesize \
  --output "$BENCHMARK_OUT" --work "$BENCHMARK_WORK"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  compare --output "$BENCHMARK_OUT" --frozen data/silver/issue-14

PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_publication.py prepare \
  --source "$TTS_SOURCE" --output "$TTS_OUT" --work "$TTS_WORK"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  synthesize --output "$TTS_OUT" --work "$TTS_WORK" --concurrency 1
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  publish --source "$TTS_SOURCE" --output "$TTS_OUT" \
  --work "$TTS_WORK" --final "$TTS_FINAL"

mkdir --parents "$ALIGNMENT_OUT" "$ALIGNMENT_WORK"
align process data/bronze/9786326186253 "$ALIGNMENT_WORK/processed-audio" \
  --log-level info
align align --ctc --emissions data/silver/issue-15/emissions \
  --audiobook "$ALIGNMENT_WORK/processed-audio" \
  --epub data/silver/issue-15/markedup.epub --language vi --granularity sentence \
  --reports "$ALIGNMENT_OUT/report.json" \
  --output "$ALIGNMENT_WORK/regenerated.epub" --time --log-level info
pixi run -e dev python -m scripts.publication \
  --source "$ALIGNMENT_WORK/regenerated.epub" --output "$ALIGNMENT_FINAL" \
  --work "$ALIGNMENT_WORK" \
  --frozen-report data/silver/issue-15/report.json \
  --regenerated-report "$ALIGNMENT_OUT/report.json"
```

Alignment consumes the retained #15 emissions rather than rerunning inference, verifies the frozen report spans and the four recorded manual boundaries, then repackages as Opus before the #17 opening repair.
The server-comparison records are in `data/silver/issue-17/tts-benchmark/benchmark-comparison.json`; the frozen-input preservation they restate is recorded by [#14](tts-feasibility.md), and no audio-quality acceptance is inferred from repeatability checks.

## Reviewed source repairs and accessibility

The corrected TTS source removes two distinct defects that source inspection confirmed in all 26 chapters: the repeated DTV-Ebook chapter header, and the detached duplicated opening initial (one single-letter paragraph per chapter duplicating the first paragraph's opening).
No legitimate single-letter paragraphs exist in this source, and the repair keeps any that do not duplicate the previous opening; it fails closed when the reviewed structure is missing or ambiguous.
Its separate chapter 12 correction changes `"P hú` to `"Phú`.
`data/work/issue-17/thang-long-noi-gian/corrected-source.epub` is regenerated from Bronze when needed; bronze inputs and frozen benchmark evidence are unchanged.
Deleting `data/work/` and publishing again from the acquired source and retained #17 Silver records produced the final TTS EPUB with 2,929 completed blocks and 10,239 Opus clips.
The three reviewed punctuation joins remain source-preserving sentence-boundary joins.

The TTS input is 48 kHz mono 16-bit PCM WAV; the seven alignment inputs are the audiobook MP3 tracks characterized in [#11](source-characterization.md).
Both publication paths encode from those inputs with libopus defaults: no project bitrate and no explicitly forced output sample rate or channel conversion.
FFmpeg/libopus performs codec-required internal resampling where the codec needs it, such as the 44.1 kHz alignment input to Opus at 48 kHz.
No new audio-quality review is claimed.

### Opening boundary measurement

The #17 alignment publication moves the spoken opening credit to visible cover text and starts biography targeting after it.
The three replacement SMIL boundaries were measured from the retained evidence, not estimated: PulseVAD (audio.cpp `pulsevad-81k-f32`, SHA-256 `574482cd225645646b9474d21a5a05eb6351efc8193d7eedb7ab241696146bec`) found the biography as one continuous speech burst 20.900–26.200 s with no internal pause at any tested threshold, and MOSS ASR (`moss-transcribe-diarize-bf16`, SHA-256 `5bc627289e2586fc2d9269afda15a305e545a4ff3512c902889be71d58e56ad5`) confirmed the spoken transcript `Nhà văn Nguyễn Huy Tưởng, sinh năm 1912, mất năm 1960.` at 20.82–26.18 s.
Word-level CTC forced alignment on the retained #15 emissions (pinned `@storyteller-platform/align` 0.2.4) placed `Nhà` at 20.90 s, `Nguyễn` at 21.42 s, and `sinh` at 22.58 s; `Quê` at 26.58 s matches the frozen boundary of the following sentence group.
Adopted at 0.1 s precision: credit 0.000–20.900, `Nhà văn` 20.900–21.400, `NGUYỄN HUY TƯỞNG` 21.400–22.600, `(1912 – 1960)` 22.600–26.100 (end unchanged).
The years clause has weak local CTC evidence (label scores 1–6 against 90+ elsewhere), so its onset is the forced-alignment result between the strong flanking anchors, with MOSS as the independent transcript check.
Raw MOSS, VAD, and word-timing outputs are retained under `data/work/issue-17/opening-locator/`.
The frozen #15 report and aligned EPUB are unchanged; Thorium playback of the re-measured opening is a pending manual check below.

Alignment title-attribute notes become linked footnotes with backlinks and their original text; duplicate title attributes are removed after materialization.
The reviewed back-cover transcription is ordinary visible text referenced by a short image alternative, rather than an oversized `alt` attribute.
This transcription is absent from the audiobook, and no narration is added to the alignment pathway.
Source-specific XHTML and stylesheet repairs are limited to their respective publications.
Discovery metadata reflects the known content: textual access for both books, visual access for the alignment book's informative images, and table-of-contents and synchronized-audio features for both.
Inspection of both final EPUBs found static images, no scripted or animated content, and no flashing or motion simulation; the sound-hazard assessment remains unknown.
Neither book declares `accessModeSufficient` while the human review needed to justify textual sufficiency remains incomplete.
Automated results do not establish completed human accessibility review or accessibility conformance.

## Automated validation

```sh
pixi run -e dev python -m pytest -q
hk check --pr

mkdir --parents data/work/issue-17/validation
for book in thang-long-noi-gian dem-hoi-long-tri; do
  podman compose run --rm --volume "$PWD/data:/data:ro,z" epubcheck \
    "/data/gold/$book.epub"
  podman compose run --rm --volume "$PWD/data:/data:z" ace \
    "/data/gold/$book.epub" \
    --outdir "/data/work/issue-17/validation/$book-ace" --force
done
```

EPUBCheck is the Compose build of `w3c/epubcheck` at git ref `a51f751b986ac424488586aae75c43d047bbdc53`; Ace is `@daisy/ace-cli@1.4.6` on the pinned Puppeteer base image (see `compose.yaml` and `containers/Containerfile.ace`).
The full declared dev suite passes 42 tests, and `hk check --pr` passes.
All 280 files in the retained frozen-evidence checksum inventory remain unchanged.
Both final EPUBs pass EPUBCheck with zero errors and warnings.
Ace flags only omitted discovery and certification metadata for both books (`schema:accessModeSufficient`, `a11y:certifiedBy`, `a11y:certifierCredential`, `a11y:certifierReport`, `dcterms:conformsTo`), whose claims await the incomplete human review.
The alignment package removes eight unused source resources while retaining its referenced cover, portrait, transcription, and seven audio tracks.

## Optional browser validation

The Playwright service and remote-Chromium configuration are documented in the "Browser validation" section of `README.md`; this section records only the #17 reader workflow.

Create `data/work/issue-17/browser-review/` and save a `cli.config.json` selecting Chromium at `ws://127.0.0.1:3000/?browser=chromium` with `browser.isolated: true` (see `compose.yaml`).

```sh
podman compose up --detach playwright
playwright-cli -s=readest open https://web.readest.com/ \
  --config=data/work/issue-17/browser-review/cli.config.json
playwright-cli -s=readest snapshot
# Select Import Books, then From Local File using the snapshot refs.
playwright-cli -s=readest upload data/gold/dem-hoi-long-tri.epub
playwright-cli -s=readest snapshot
playwright-cli -s=readest console
playwright-cli -s=readest requests
```

## Reader validation results and limitations

Earlier Readest imports of both publications transferred successfully but remained at "Loading…"; a bronze source control imported successfully.
The retained browser diagnostics show no EPUB parsing error, and the exact cause of Readest's behavior is unknown.
Manual Thorium Reader review found earlier packages of both publications opened and read successfully, so the Readest observation is reader-specific.
Pending manual checks: the re-measured alignment opening in Thorium (credit highlighting, biography transitions at 20.9/21.4/22.6 s), the rebuilt TTS Gold chapter openings, and the broader synchronization playback, audio-quality, and human accessibility reviews.
One transcription uncertainty remains: the spoken credit reader name is heard as "Ngọc Hân" by CTC and "Ngọc Hưng" by MOSS; the displayed credit keeps the earlier reviewed transcription.
The PR remains draft until the required manual checks are completed.
