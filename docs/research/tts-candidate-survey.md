# TTS candidate survey - September 2026

**Purpose.** Record the current directly usable TTS landscape relevant to Issue [#13](https://github.com/itskyf/lyrepub/issues/13) and the resulting system-selection decision. This is survey and selection evidence, not a multi-model experiment. Follow [source characterization](source-characterization.md) for the selected material and [protocol](protocol.md) for the research method.

**Evidence notation.** **D** = documented by the model author or official implementation; **A** = author-reported or author-demonstrated behavior; **P** = behavior not yet verified by this project. Sources were checked through 27 September 2026. Author claims are not LyrePub results.

## Selection

**VieNeu-TTS v3 Turbo** is selected for the TTS pathway. Its current repository describes v3 Turbo as the latest open-source VieNeu-TTS release, with Vietnamese/English support, 48 kHz output, built-in preset voices, and optional reference voice cloning ([runtime](https://github.com/pnnbao97/VieNeu-TTS), [checkpoint](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo)). Candidate selection is complete; the exact evaluated configuration and evidence are frozen in #14 and recorded in the [TTS feasibility record](tts-feasibility.md).

The selected narration voice is the built-in preset **`Quỳnh Anh`**, which is present in the current v3 Turbo preset set. This avoids a reference-audio dependency.

The voice decision comes from focused pre-experiment listening, not a scored comparison: the cloned voices tested for this coursework sounded less natural for audiobook narration in **prosody**, particularly speaking rate and pause placement, than the preset voices auditioned. Human review selected `Quỳnh Anh` (female, Northern Vietnamese, storytelling) as the preferred preset; it retains the same main feasibility limitations. This is a project-specific selection rationale, not evidence that preset voices or VieNeu-TTS are generally superior to voice cloning.

No further TTS candidate comparison is planned. The completed feasibility review and the frozen configuration evaluated by #14 are recorded in the [TTS feasibility record](tts-feasibility.md).

## Candidate landscape

The remaining entries preserve decision-relevant survey evidence. They are alternatives, not required experiment arms.

| Candidate and primary source | Relevant documented evidence and constraint | Disposition |
| --- | --- | --- |
| **[VieNeu-TTS v3 Turbo](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo)** ([runtime](https://github.com/pnnbao97/VieNeu-TTS)) | D: Vietnamese/English, preset voices, reference cloning, local CPU ONNX or CUDA paths, 48 kHz. Current runtime lists v3 Turbo as the latest open-source release. | **Selected.** Use preset `Quỳnh Anh`; freeze exact revision and settings in #14. |
| **[KorvaTTS](https://github.com/dogenthq/KorvaTTS)** | D: Vietnamese-first ONNX Runtime system, Vietnamese/English code-switching, bundled preset voices, 44.1 kHz, Apache-2.0 code and weights. Voice cloning is currently roadmap work rather than a released capability. | Surveyed alternative; no run required after VieNeu-TTS selection. |
| **[ZeroTTS](https://huggingface.co/zeroweight-ai/ZeroTTS)** ([code](https://github.com/zeroweight-ai/ZeroTTS)) | D: Vietnamese local ONNX path and shipped voice latents; A: raw numbers/dates/acronyms and long-form examples. Current release does not publish the encoder needed to create new local clones. | Not promoted. |
| **[VoxCPM2](https://huggingface.co/openbmb/VoxCPM2)** | D: multilingual synthesis including Vietnamese, English, and French; reference voice and text-directed voice paths. Larger runtime than needed for the selected path. | Not promoted. |
| **[G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice)** | D: Vietnamese-optimized OmniVoice adaptation with voice cloning/design. The checkpoint is gated; access is available for this coursework. Its dependency chain includes OmniVoice and the Higgs Audio tokenizer, so effective rights would still need re-checking if promoted. | Access fallback no longer needed; not selected. |
| **[OmniVoice base](https://huggingface.co/k2-fsa/OmniVoice)** / **[KhanhTTS-OmniVoice](https://huggingface.co/kjanh/KhanhTTS-OmniVoice)** | D: OmniVoice-family multilingual/reference-cloning paths. The base model card states noncommercial terms for pretrained weights. | No longer needed as G-OmniVoice access fallbacks; not promoted. |
| **[Higgs TTS 3 4B](https://huggingface.co/bosonai/higgs-tts-3-4b)** | D: multilingual support including Vietnamese/English/French and broad expressive controls; heavier runtime and noncommercial/research licensing constraints. | Reserve only. |
| **[ZONOS2](https://huggingface.co/Zyphra/ZONOS2)** | D: Vietnamese support and local backends; Vietnamese is not in its built-in text-normalizer language list. | Reserve only. |
| **[Confucius4-TTS](https://huggingface.co/netease-youdao/Confucius4-TTS)** | D: Vietnamese and multilingual reference cloning; official preprocessing warrants checking for Vietnamese number handling. | Reserve only. |
| **[dots.tts SOAR](https://huggingface.co/dots-studio/dots.tts-soar)** | D: Vietnamese support and reference-conditioned synthesis; long-input suitability remains P for this source. | Reserve only. |
| **[Fish Audio S2 Pro](https://huggingface.co/fishaudio/s2-pro)** | D: Vietnamese among broad multilingual support with rich controls; substantially heavier runtime and research/noncommercial terms. | Reserve only. |
| **[MOSS-TTS v1.5](https://huggingface.co/OpenMOSS-Team/MOSS-TTS-v1.5)** | D: Vietnamese multilingual support and long-form claims; larger model/runtime than needed for the selected path. | Reserve only. |
| **[Gwen-TTS 0.6B](https://huggingface.co/g-group-ai-lab/gwen-tts-0.6B)** | D: Vietnamese-adapted Qwen3-TTS path with presets/reference conditioning. Adaptation-specific behavior still requires its own verification. | Reserve only. |

Other checked Vietnamese adaptations and hosted services do not add a capability needed to justify reopening model selection. They would be revisited only if a blocking VieNeu-TTS limitation required another system.

## Survey conclusion

Candidate selection is complete. VieNeu-TTS v3 Turbo with preset `Quỳnh Anh` is the selected route, with explicitly recorded source-justified processing; this survey remains the selection evidence, and the evaluated configuration belongs to #14 and the [TTS feasibility record](tts-feasibility.md).
