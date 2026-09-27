# Alignment-support survey - September 2026

**Purpose.** Record the directly usable alignment landscape relevant to Issue [#13](https://github.com/itskyf/lyrepub/issues/13) and the resulting route-selection strategy for the existing-audiobook pathway. This is survey evidence, not an ASR benchmark or alignment experiment. Follow [source characterization](source-characterization.md) for the selected EPUB/audiobook structure and [protocol](protocol.md) for the research method.

**Evidence notation.** **D** = documented by the tool/model author or official implementation; **A** = author-reported or author-demonstrated behavior; **P** = behavior not yet verified by this project. Sources were checked through 27 September 2026. Author claims are not LyrePub results.

## Selected implementation family

**Storyteller `stalign`** is selected as the alignment implementation family. Its current source exposes two materially different native route families:

- **CTC emissions -> forced alignment**, selected as the first route;
- **transcription -> text matching/alignment**, with built-in `whisper.cpp` and other transcription backends.

The current CTC pipeline can generate emissions with a multilingual Wav2Vec2/MMS forced-aligner model and align EPUB reference text directly, without first producing an ASR transcript ([CLI pipeline](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/cli/bin.ts), [emission options](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/emit/parse.ts), [alignment options](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/align/parse.ts)). This is the smallest native route because it does not require an external ASR adapter.

Issue #15 therefore begins with native CTC. If that route produces timing output usable for protocol evaluation without a blocking material failure on the selected source, freeze it and stop route exploration. If a blocking material failure is observed, retain the evidence and stop for project-owner review before promoting another documented route. Do not implement an automatic fallback chain.

## Route landscape

The remaining entries are escalation evidence, not required experiment arms.

| Route or component | Relevant documented evidence and constraint | Disposition |
| --- | --- | --- |
| **`stalign` native CTC + MMS forced-aligner emissions** | D: native emissions and CTC alignment path; current default emission model is `onnx-community/mms-300m-1130-forced-aligner-ONNX`. Reference EPUB text is an explicit forced-alignment input. Vietnamese audiobook suitability remains P. | **First route for #15.** |
| **`stalign` + built-in `whisper.cpp`** | D: native transcription route with multilingual Whisper models and Storyteller's own transcription/timeline format. Processor parallelism may affect timing accuracy, so materially relevant settings must be recorded. | First native escalation option if CTC has a blocking failure and review approves it. |
| **[PhoASR-whisper-small](https://huggingface.co/Qualcomm-AI-Research/PhoASR-whisper-small) -> Storyteller transcription format** | D: Vietnamese-specific Whisper checkpoint with word timestamps through its documented Transformers path. Requires a deterministic adapter to Storyteller's existing transcript/timeline shape. | External-ASR escalation option; do not implement unless justified by observed failure. |
| **[NVIDIA Parakeet-CTC-0.6B-Vietnamese](https://huggingface.co/nvidia/parakeet-ctc-0.6b-Vietnamese) -> Storyteller transcription format** | D: Vietnamese-specific CTC ASR with character, word, and segment timestamps. Heavier NeMo/PyTorch environment. | Conditional diagnostic option if timing remains the demonstrated blocker. |
| **[easyaligner](https://github.com/kb-labb/easyaligner)** | D: standalone forced alignment for long audio and reference/ASR transcripts, including partial-region workflows. Duplicates much of the native CTC role and needs separate publication integration. | Reserve only if the failure is specific to Storyteller's CTC implementation. |
| **[Qwen3-ASR](https://qwen.ai/blog?id=qwen3asr) / `audio.cpp`** | D: Vietnamese ASR text is supported, but the associated Qwen forced-aligner language set does not currently establish Vietnamese timestamp support. | Not a current escalation path. |
| **[VibeVoice-ASR](https://github.com/microsoft/VibeVoice/blob/main/docs/vibevoice-asr.md)** | D: multilingual long-form structured ASR, including Vietnamese evidence, but with a much heavier model/runtime and an interface that does not simplify the present task. | Not justified for this coursework path. |

Other Vietnamese ASR adaptations found during the survey remain alternatives only. Better transcription benchmark results do not by themselves establish better EPUB/audio alignment and do not justify a broad ASR comparison.

## Source-material implications

The selected audiobook already contains the alignment conditions that matter for feasibility:

- audiobook tracks and EPUB spine documents are not one-to-one;
- track 1 spans multiple spine documents;
- the audiobook contains an opening announcement absent from the EPUB;
- some headings or publication text may be verbalized differently;
- navigational coverage is not equivalent to synchronization coverage.

These observations are recorded in [source characterization](source-characterization.md) and should not be duplicated as new benchmark categories. They are used in #15 to determine whether a route tolerates ordinary source/audio disagreement without silent repair.

The CTC route uses EPUB reference text explicitly, which is permitted by the protocol for forced alignment. A transcription-driven route, if later approved, must preserve its own recognized text; do not silently substitute EPUB reference text into ASR output.

## What remains for #15

The survey selects the implementation family and first route but does not establish that CTC works on the selected Vietnamese audiobook.

The initial feasibility run should retain enough evidence to inspect:

- whether the route runs reproducibly with the selected EPUB and audiobook;
- synchronization coverage and unmatched source/audio regions;
- behavior around the known inserted announcement and cross-document track;
- timing output and reports needed for protocol evaluation;
- any required chapter assistance or other human intervention;
- materially relevant tool/model settings.

No numeric pass threshold is introduced here. If a blocking material failure is observed, retain the failing output and report the failure before changing routes. Route selection, synchronization granularity, benchmark items, timing-error verification procedure, and human-assistance conditions are frozen before the reported #15 evaluation.

## Survey conclusion

The survey does not justify a multi-candidate alignment benchmark. Storyteller `stalign` is the selected implementation family, with native CTC as the first route because it is the smallest direct path from audiobook audio and EPUB reference text to alignment output. Other routes remain documented escalation options only when an observed failure creates a specific need.
