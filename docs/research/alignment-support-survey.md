# Alignment-support survey - September 2026

**Purpose.** Record the directly usable alignment landscape relevant to Issue [#13](https://github.com/itskyf/lyrepub/issues/13) and the resulting route-selection strategy for the existing-audiobook pathway. This is survey evidence, not an ASR benchmark or alignment experiment. Follow [source characterization](source-characterization.md) for the selected EPUB/audiobook structure and [protocol](protocol.md) for the research method.

**Evidence notation.** **D** = documented by the tool/model author or official implementation; **A** = author-reported or author-demonstrated behavior; **P** = behavior not yet verified by this project. Sources were checked through 27 September 2026. Author claims are not LyrePub results.

## Selected implementation family

**Storyteller `stalign`** is selected as the alignment implementation family. Its current source exposes two materially different native route families:

- **CTC emissions -> forced alignment**, selected and later frozen by Issue #15;
- **transcription -> text matching/alignment**, with built-in `whisper.cpp` and other transcription backends.

The current CTC pipeline can generate emissions with a multilingual Wav2Vec2/MMS forced-aligner model and align EPUB reference text directly, without first producing an ASR transcript ([CLI pipeline](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/cli/bin.ts), [emission options](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/emit/parse.ts), [alignment options](https://github.com/smoores-dev/storyteller/blob/main/libraries/align/src/align/parse.ts)). This is the smallest native route because it does not require an external ASR adapter.

Issue #15 subsequently froze native CTC after the selected-source run produced usable timing output without a blocking material failure. No escalation route was needed; the executed configuration and results are recorded in [alignment validation](alignment-validation.md).

## Route landscape

The remaining entries are escalation evidence, not required experiment arms.

| Route or component | Relevant documented evidence and constraint | Disposition |
| --- | --- | --- |
| **`stalign` native CTC + MMS forced-aligner emissions** | D: native emissions and CTC alignment path; current default emission model is `onnx-community/mms-300m-1130-forced-aligner-ONNX`. Reference EPUB text is an explicit forced-alignment input. | **Selected and frozen by #15.** |
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

These observations are recorded in [source characterization](source-characterization.md) and should not be duplicated as new benchmark categories. They informed the #15 feasibility check and reported evaluation; observed behavior and limitations are recorded in [alignment validation](alignment-validation.md).

The selected CTC route uses EPUB reference text explicitly, which is permitted by the protocol for forced alignment. No transcription-driven escalation route was needed.

## Survey conclusion

Candidate selection is complete. Storyteller `stalign` native CTC is the selected and frozen alignment route because it is the smallest direct path from audiobook audio and EPUB reference text to alignment output. The other routes remain survey context rather than experiment arms; the executed configuration and results belong to #15 and [alignment validation](alignment-validation.md).
