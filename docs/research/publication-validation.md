# Final publication reproduction and validation

[Issue #17](https://github.com/itskyf/lyrepub/issues/17) records the publication decisions.
New reproducible outputs use `data/publications/thang-long-noi-gian/`, `data/publications/dem-hoi-long-tri/`, and `data/publications/tts-benchmark/`.
Historical bronze inputs and frozen `data/silver/issue-14/`, `issue-14-reported/`, and `issue-15/` evidence retain their existing names and content.
Full-book source mapping, frontend inputs, bronze block seeds, audio references, and timings are recorded in `sentences.json`; benchmark records remain `cases.json`.
`work/` contains disposable targeting and transcoding inputs; `data/publications/diagnostics/` and `browser-review/` contain focused verification material.

## Reproduction

Set `TTS_SOURCE`, `MODEL_GGUF`, and `VOICE_DIR` to the existing bronze TTS book, pinned BF16 checkpoint, and Quỳnh Anh voice assets.
Use fresh output directories for a new run.
The Compose audio.cpp configuration loads these assets from `data/models/VieNeu-TTS-v3-Turbo-GGUF/` on CUDA with one inference thread.
Python retains the frozen VieNeu normalization, chunking, phonemization, and audio joining; audio.cpp owns inference.
VieNeu 3.8.3, SEA-G2P 0.10.0, and `zapros[pyreqwest]` 0.19.0 are script-local PEP 723 dependencies, not project or development dependencies.
The inline environment also declares the pinned sentence frontend and its Torch requirement.
Dictionary content, checkpoint, and voice hashes are verified; installed package versions are recorded as frontend provenance without redundant version assertions.

```sh
podman compose up --detach audiocpp playwright
curl --fail --silent http://127.0.0.1:8080/health
curl --fail --silent 'http://127.0.0.1:8080/v1/models?include_session_options=true'

TTS_OUT=data/publications/thang-long-noi-gian
ALIGNMENT_OUT=data/publications/dem-hoi-long-tri
BENCHMARK_OUT=data/publications/tts-benchmark

PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  prepare --source-epub "$TTS_SOURCE" --output "$BENCHMARK_OUT"
PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_benchmark.py synthesize \
  --output "$BENCHMARK_OUT" --model "$MODEL_GGUF" --voice-dir "$VOICE_DIR"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_benchmark.py \
  compare --output "$BENCHMARK_OUT" --frozen data/silver/issue-14

PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  pixi run -e dev uv run --script scripts/tts_publication.py prepare \
  --source "$TTS_SOURCE" --output "$TTS_OUT"
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  synthesize --output "$TTS_OUT" --model "$MODEL_GGUF" --voice "$VOICE_DIR" \
  --concurrency 1
PYTHONPATH=src:. pixi run -e dev uv run --script scripts/tts_publication.py \
  publish --source "$TTS_SOURCE" --output "$TTS_OUT"

mkdir --parents "$ALIGNMENT_OUT/work"
align process data/bronze/9786326186253 "$ALIGNMENT_OUT/work/processed-audio" \
  --log-level info
align align --ctc --emissions data/silver/issue-15/emissions \
  --audiobook "$ALIGNMENT_OUT/work/processed-audio" \
  --epub data/silver/issue-15/markedup.epub --language vi --granularity sentence \
  --reports "$ALIGNMENT_OUT/report.json" \
  --output "$ALIGNMENT_OUT/work/regenerated.epub" --time --log-level info
pixi run -e dev python -m scripts.publication \
  --source "$ALIGNMENT_OUT/work/regenerated.epub" --output "$ALIGNMENT_OUT" \
  --frozen-report data/silver/issue-15/report.json \
  --regenerated-report "$ALIGNMENT_OUT/report.json"
```

One Zapros async client with `AsyncPyreqwestHandler` and one semaphore serve the complete synthesis run.
`--concurrency` must be positive and defaults to one; the server serializes inference for its loaded model.
Every request carries the prepared phonemes, bronze block seed, exact UTF-8 chunk budget, and frozen sampling options.
HTTP errors, non-WAV responses, invalid PCM, and preprocessing failures stop the run and remain in its records.
Completed blocks can resume only with the same verified runtime.
No Python inference fallback is provided.
Alignment consumes retained emissions rather than rerunning inference, and verifies the frozen report spans and four recorded manual timing boundaries.
The regenerated report matches the frozen report, and all 3,382 SMIL timing and text-reference tuples remain unchanged through Opus packaging.

## Runtime and benchmark comparison

The inspected Compose audio.cpp image is `15034226bb05d727758cc455ece59cf5fe50a7452ad1f189c7edb77951d37e79`, built from upstream revision `f99bd1e1f393999a3ce8abf5029b1e1d9af1cfe1`.
The original frozen evidence used revision `955c8725c611d511774e6be132aff6609163b2d2`; the current comparison is reported separately and does not redefine that evidence.
`runtime.json` records the actual Compose image and digest, loaded `vieneu_v3_turbo` model path, server configuration, frozen asset hashes, sampling options, and separate Python frontend provenance before synthesis.
The loaded model is `vieneu-v3-turbo-bf16.gguf` with Quỳnh Anh conditioning, CUDA, and the frozen 0.8 temperature, top-k 25, top-p 0.95, 1.2 repetition penalty, 64-frame repetition window, 300-token cap, and two babble retries.
The server comparison preserves all 118 frozen sentence inputs, frontend chunks, source mappings, and clip durations.
Decoded Opus PCM matches for 117 sentences; `s5-b9` sentence 39 reproduces the previously reviewed full-run recording rather than the older isolated recording.
A focused curl repeat produces the same raw PCM as the server benchmark and previous full run.
The differing older isolated waveform is retained, so byte-identical reproduction of all frozen recordings is not claimed.
`benchmark-comparison.json` records each sentence comparison.
The reviewed full-book recording is checked separately from the frozen benchmark.
All 3,031 blocks and 10,341 sentence clips complete through the server without synthesis failures.
Of the 10,340 unchanged sentences, 10,337 regenerated WAV clips match the reviewed full run byte-for-byte.
Three unchanged sentence waveforms differ: `s10-b4` sentence 1, `s14-b4` sentence 0, and `s21-b4` sentence 0.
Their duration differences are 0.160, -0.240, and 0.000 seconds, respectively, and focused curl repeats reproduce all three server PCM results exactly.
Their authored text, phonemes, seeds, sampling settings, checkpoint, voice assets, and Python frontend are identical to the earlier reviewed run.
The [upstream runtime comparison](https://github.com/0xshug0/audio.cpp/compare/955c8725c611d511774e6be132aff6609163b2d2...f99bd1e1f393999a3ce8abf5029b1e1d9af1cfe1) contains shared sampler and prefill changes but no VieNeu model-source changes; the exact cause of the waveform differences is not established.
The server execution path is retained, and no new audio-quality acceptance is inferred from these repeatability checks.

## Reviewed source repairs and accessibility

The final TTS source corrects the opening `"P hú` to `"Phú` in chapter 12 and removes its duplicate standalone `"P` paragraph.
The chapter 1 standalone `V` duplicates the initial of the immediately preceding complete sentence beginning "Vừa bước vào tới cửa cung Thánh từ" and is removed without changing that sentence or the following dialogue.
`corrected-source.epub` and its checksum make these final-publication changes explicit; source offsets refer to this corrected copy while inference seeds retain the corresponding bronze block indices.
These edits do not change bronze inputs or frozen benchmark evidence, and exact-text preservation is claimed only outside the reviewed corrections.
The reviewed punctuation joins remain source-preserving sentence-boundary joins.
All other previously reviewed TTS audio is accepted.
Alignment title-attribute notes become linked footnotes with backlinks and their original text; duplicate title attributes are removed after materialization.
The reviewed back-cover transcription is ordinary visible text referenced by a short image alternative, rather than an oversized `alt` attribute.
This transcription is absent from the audiobook, and no narration is added to the alignment pathway.
Source-specific XHTML and stylesheet repairs are limited to their respective publications.
Discovery metadata reflects the known content: textual access for both books, visual access for the alignment book's informative images, and table-of-contents and synchronized-audio features for both.
The alignment book also declares its image alternatives; static content excludes flashing and motion simulation, while the sound-hazard assessment remains unknown.
Neither book declares `accessModeSufficient` while the human review needed to justify textual sufficiency remains incomplete.
Automated results do not establish completed human accessibility review or accessibility conformance.

## Automated validation and package inspection

```sh
pixi run -e dev python -m pytest -q tests/test_publication.py \
  tests/test_tts_benchmark.py tests/test_sentence_targets.py tests/test_media_overlays.py
pixi run -e dev python -m pytest -q
hk check --pr

for book in thang-long-noi-gian dem-hoi-long-tri; do
  podman compose run --rm --volume "$PWD/data:/data:ro,z" epubcheck \
    "/data/publications/$book/final.epub"
  podman compose run --rm --volume "$PWD/data:/data:z" ace \
    "/data/publications/$book/final.epub" \
    --outdir "/data/publications/$book/ace" --force
done
```

Normal pytest checks reusable source mapping, coverage, all three approved punctuation joins, fail-closed source corrections, nested navigation, Opus packaging, manifest/SMIL references, and frozen alignment timings using only declared project and dev dependencies.
The focused suite passes 32 tests and the full suite passes 43 tests.
`hk check --pr` still fails Biome formatting on the unchanged mise-generated package files and `containers/audiocpp.json`; Python checks pass, and those out-of-scope files were not changed.
All 280 files in the retained frozen-evidence checksum inventory remain unchanged.
Actual frontend and inference integration runs through the inline-uv benchmark and publication commands.
Both final EPUBs pass Compose EPUBCheck with zero errors and warnings.
Ace flags the omitted `accessModeSufficient` property, a SHOULD discovery property whose textual claim awaits human review.
Package inspection checks ZIP sizes and duplicate entries, manifest resources, local references, reachable assets, audio references, and overlay duration totals.
Eight unused alignment source resources, including three byte-identical image variants, are removed from the final package while its referenced cover, portrait, transcription, and seven audio tracks remain available.
The alignment package has 38 resources, 35 manifest entries, seven referenced Opus tracks, and 3,382 clips totaling 16,446.44 seconds of overlay intervals.
It contains 167,904,274 file bytes, with 167,899,302 compressed and 170,887,746 uncompressed resource bytes.
Its encoded audio tracks total 16,446.603229 seconds, and package inspection finds no missing manifest resources, missing local references, duplicate entries, byte-identical resources, unreferenced audio, or unreachable manifest resources.
The TTS package has 10,399 file resources, 10,396 manifest entries, 10,341 referenced Opus clips, and 26 SMIL documents.
It contains 610,169,986 file bytes, with 608,510,340 compressed and 612,212,676 uncompressed resource bytes.
Its encoded audio resources total 43,891.6765 seconds; the rounded overlay intervals total 43,886.506 seconds.
Its three original ZIP directory markers are listed separately from file resources.
It has no missing references or manifest resources, unmanifested files, duplicate entries, byte-identical file resources, unreferenced audio, or unreachable manifest resources.
Final package inventories are retained as `package-inspection.json` beside each EPUB.

## Readest validation

The repository Playwright service uses `mcr.microsoft.com/playwright:v1.63.0` and Playwright 1.63.0 `run-server`, with `init`, Chromium host IPC, and a loopback-published port 3000.
Its healthcheck probes that local server port without launching a browser; the 60-second startup allowance follows [Playwright's web-server default](https://playwright.dev/docs/test-webserver).
The mise-managed CLI 0.1.19 supplies a compatible Playwright 1.63 client.
Its npm release and integrity were checked against the upstream tag and npm registry before adding narrowly versioned provenance exceptions for that release and its two published alpha dependencies.
The remote configuration explicitly selects Chromium through the server's supported endpoint query and creates an isolated context.
No browser is installed on the host, and EPUBs transfer through the CLI upload operation without an EPUB volume mount.

Create `data/publications/browser-review/` and save the following JSON as `cli.config.json` there.

```json
{
  "browser": {
    "browserName": "chromium",
    "isolated": true,
    "remoteEndpoint": "ws://127.0.0.1:3000/?browser=chromium"
  }
}
```

```sh
playwright-cli -s=readest open https://web.readest.com/ \
  --config=data/publications/browser-review/cli.config.json
playwright-cli -s=readest snapshot
# Select Import Books, then From Local File using the snapshot refs.
playwright-cli -s=readest upload data/publications/dem-hoi-long-tri/final.epub
playwright-cli -s=readest snapshot
playwright-cli -s=readest console
playwright-cli -s=readest requests
```

Readest import and playback checks are focused validation evidence, not a new browser test suite.
The original 168,645,341-byte alignment package remains at "Loading…" after successful file transfer; snapshots, console logs, and request inspection were retained before removing unused resources.
The previously reviewed 167,904,216-byte alignment package also remained at "Loading…" after ten minutes, and a retry after reloading the page remained there for over an hour.
The previously reviewed 610,169,975-byte TTS EPUB transferred successfully through the same real import flow and remained at "Loading…" for over ten minutes.
Neither previously reviewed package completed import or became available to open, so final rendering, navigation, corrected-text presentation, synchronized playback, and highlighting remain unverified in Readest for the rebuilt packages.
The observed import consoles contain no EPUB parsing error; request inspection again records the blocked worker request without establishing its causal role.
A separate bronze source control imports successfully; its first opening times out fetching Readest's reader-page JavaScript chunk, and reload recovers the reader.
A blocked service-worker request and an unrelated analytics DNS failure are recorded but are not established as causes of the final-publication import hang.
The valid package and successful source control distinguish this observed reader/import limitation from evidence of malformed EPUB resources, without proving its exact cause.
Audio quality and reviewed sentence-level synchronization are unchanged by this investigation.
The PR remains draft until final reader rendering, navigation, synchronized playback/highlighting, and remaining human accessibility checks can be completed.
