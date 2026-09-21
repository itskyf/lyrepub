# Research Framework for Vietnamese TTS in Accessible EPUB 3.3 Audiobook Production

## 1. Goal, Baseline, and Principles

### Goal

Convert an arbitrary Vietnamese EPUB book into an accessible EPUB 3.3 publication with synchronized synthetic audio using Media Overlays, **primarily for blind and print-disabled readers**.

The project evaluates and integrates existing TTS systems only. Training or fine-tuning a TTS model is outside the core scope.

### Standards baseline

The implementation target is: **EPUB 3.3 + Media Overlays + EPUB Accessibility 1.1**

EPUB 3.3 is the current EPUB Recommendation. EPUB Accessibility 1.1 is the current accessibility Recommendation; EPUB Accessibility 1.2 remains a Candidate Recommendation as of September 2026. [R1–R3]

### Principles

1. **Accessibility before expressiveness.** Content completeness, reading order, navigation, intelligibility, pronunciation and synchronization take priority over dramatic narration.
2. **Requirements come from the book.** Do not add code-switching, character processing or other specialized stages unless target-book analysis shows that they matter.
3. **Evaluate deployable systems, not architecture popularity.**
4. **Keep requirements traceable:**

```text
Book phenomenon
      ↓
Requirement
      ↓
Benchmark case
      ↓
Evaluation
```

5. **Do not hide trade-offs in an arbitrary weighted score.** Accessibility-critical requirements are acceptance gates.
6. **Do not add an NLP stage unless it changes the final audiobook or answers a research question.**

---

## 2. System and Key Design Decisions

### 2.1 Core pipeline

```text
Vietnamese EPUB
      ↓
Parse and preserve structure
      ↓
Segment + normalize text
      ↓
Handle pronunciation/language
      ↓
TTS synthesis
      ↓
Generate timings + Media Overlays
      ↓
Repackage EPUB 3.3
      ↓
Validate accessibility and playback
```

The pipeline must preserve:

- spine reading order;
- table of contents and headings;
- chapters, sections and paragraphs;
- relevant lists, notes, tables and page markers;
- language metadata;
- meaningful text alternatives for non-text content.

Media Overlays must retain the mapping:

$$
\text{EPUB fragment}
\leftrightarrow
\text{audio segment}
$$

Sentence or paragraph-level synchronization is preferred. Word-level alignment is unnecessary unless explicitly required.

### 2.2 Text and pronunciation handling

Handle phenomena materially present in the book:

- numbers, dates, times, currency and units;
- abbreviations and symbols;
- Vietnamese pronunciation and tones;
- proper names and rare/domain terms;
- foreign words and code-switching when present.

Text normalization and pronunciation are evaluated separately: fluent speech may still express the wrong interpretation or pronunciation.

Pronunciation overrides may use controls supported by the selected TTS system. EPUB/SSML pronunciation mechanisms are optional rather than a reason to redesign the core pipeline. [R4]

### 2.3 Narration strategy

#### Core decision: single narrator

The **must-have baseline is one stable narrator voice for the whole book**.

This does not require monotonous delivery. Narration should still use suitable phrasing, pauses, stress and intonation to distinguish narrative text from dialogue.

NLS production guidance specifically expects narration to distinguish narrative, dialogue and characters using timing, stress, emphasis and inflection without making the performance distracting. Character voices, if used, should remain clear, consistent and appropriate rather than exaggerated. [R5]

#### Optional: character-specific voices

Character voices are **not an accessibility requirement**. They are an optional experiment when:

1. dialogue is materially important in the target books; and
2. the project explicitly studies narration strategy.

Use only:

```text
Narration → narrator voice

Major recurring speaker
    → persistent character voice

Minor / unknown / uncertain speaker
    → narrator voice
```

Do **not** make:

```text
every detected character → unique voice
```

a core requirement.

The purpose of character inventory is therefore only to identify **recurring dialogue speakers that may benefit from persistent voice identity**.

Recent S-VoCAL research motivates character-specific voices as a possible aid to character identification, but also shows that detailed automatic voice casting requires difficult inference about fictional characters. Such attribute inference is outside the core project. [R6]

#### Speaker-attribution risk

Multi-character synthesis introduces:

$$
\text{quote}
\rightarrow
\text{speaker attribution}
\rightarrow
\text{voice}
$$

An attribution error can cause one character's line to be spoken using another character's voice.

A 2026 narrative-dialogue study reported 72.5% attribution accuracy with BookNLP alone and 90% after FastCoref preprocessing on its small validation sample. These results demonstrate that attribution is fallible and must not be assumed to transfer directly to Vietnamese novels. [R7]

Therefore, if character voices are tested:

- evaluate speaker attribution on a manually verified subset;
- use `unknown/uncertain → narrator` as fallback;
- track only major recurring speakers;
- do not build a complex character knowledge graph.

#### Multiple POV narrators

Multiple narrators are a separate case from dialogue voices.

When a book is clearly divided into distinct character viewpoints, different narrator voices may be assigned consistently to those POVs. Current NLS guidance explicitly permits this structure while requiring consistent narrator–POV mapping. [R5]

---

## 3. Target-Book Analysis and Requirement Derivation

The target EPUB determines what must be tested.

### 3.1 Mandatory analysis

Inspect:

| Area               | What to measure or inspect                             |
| ------------------ | ------------------------------------------------------ |
| Structure          | chapters, headings, paragraphs, lists, notes, tables   |
| Length             | sentence and paragraph length distributions            |
| Text normalization | numbers, dates, units, abbreviations, symbols          |
| Lexicon            | proper names, rare/domain vocabulary                   |
| Language           | foreign/code-switched spans                            |
| Narration          | punctuation, dialogue frequency, long passages         |
| Accessibility      | navigation, text alternatives, synchronization targets |

Report distributions and difficult tails rather than only averages.

A separate linguistic ontology or exhaustive external-corpus EDA is unnecessary. External Vietnamese resources may be used when they help explain a specific pronunciation or linguistic risk.

### 3.2 Conditional dialogue analysis

**Only if character-aware narration is being considered**, additionally inspect:

- number of dialogue turns;
- number of recurring speakers;
- how concentrated dialogue is among major speakers;
- proportion of ambiguous/unknown speakers.

Do not perform full character extraction before establishing that dialogue is important.

### 3.3 Convert observations into tests

| Observation                                        | Requirement                | Test                      |
| -------------------------------------------------- | -------------------------- | ------------------------- |
| frequent numbers/dates                             | correct normalization      | spoken-form correctness   |
| many proper names                                  | pronunciation robustness   | name subset               |
| code-switching present                             | multilingual handling      | observed foreign spans    |
| long sentences                                     | synthesis robustness       | tail-length examples      |
| long passages                                      | long-form stability        | passage test              |
| frequent dialogue                                  | clear dialogue/narration   | dialogue passages         |
| complex EPUB structure                             | accessibility preservation | end-to-end EPUB test      |
| recurring speakers + optional character experiment | speaker consistency        | annotated dialogue subset |

Only observed or accessibility-critical phenomena become major benchmark strata.

---

## 4. TTS Survey and Benchmark

### 4.1 Candidate eligibility

A candidate must provide:

- usable Vietnamese synthesis;
- accessible inference through checkpoint, software or API;
- licensing compatible with the experiment;
- output suitable for offline EPUB generation.

Require additional capabilities only when justified:

- code-switching;
- pronunciation overrides;
- style/prosody controls;
- multiple voices.

Streaming latency, concurrency, autoscaling and production serving are irrelevant to the main coursework question.

For each shortlisted system record:

| Field                  | Purpose               |
| ---------------------- | --------------------- |
| system/version         | reproducibility       |
| Vietnamese evidence    | language support      |
| inference access       | feasibility           |
| pronunciation controls | correction ability    |
| multilingual support   | if required           |
| long-form evidence     | audiobook suitability |
| licensing/restrictions | practical use         |
| project benchmark      | direct comparison     |

Keep the shortlist small enough that every candidate can be evaluated under the same protocol.

Do not compare MOS values from unrelated papers as if they were directly comparable.

### 4.2 Benchmark

Use three compact sets.

#### Representative set

Ordinary passages sampled from the target-book distribution.

Purpose: evaluate normal audiobook use.

#### Challenge set

Difficult cases identified by analysis, such as:

- names;
- numbers;
- rare terms;
- long sentences;
- code-switching;
- dialogue-heavy passages.

Purpose: diagnose risks.

Do not add challenge categories merely because they are popular in TTS literature.

#### End-to-end EPUB set

A small publication subset exercising:

- navigation/headings;
- paragraph order;
- relevant notes/lists/tables;
- required text alternatives;
- Media Overlay references and playback.

Purpose: verify that TTS output can become an accessible publication.

Do not prescribe arbitrary sampling percentages. Freeze the final evaluation set before final comparison.

---

## 5. Experimental Protocol

### 5.1 Primary experiment

Evaluate each candidate using the configuration that could actually be deployed:

```text
EPUB
 → common structural extraction
 → common segmentation
 → permitted normalization/pronunciation corrections
 → candidate TTS
 → common Media Overlay generation
 → common evaluation
```

Record model-specific interventions.

A single development loop may be used to correct segmentation, normalization or configuration errors before freezing the final setup.

### 5.2 Optional diagnostic

When the source of an error is unclear:

```text
raw text
   ↓
manually corrected spoken form
   ↓
TTS
```

If the corrected form synthesizes correctly, the main problem lies in frontend interpretation rather than acoustic synthesis.

This is a diagnostic tool, not a second full benchmark.

### 5.3 Optional narration experiment

Only for dialogue-heavy books and an explicit narration-strategy research question.

Compare at most:

#### **A. Single narrator**

```text
all text → one narrator voice
```

#### **B. Selected character voices**

```text
narration → narrator

major verified speaker → persistent voice

minor / uncertain speaker → narrator
```

A full-cast configuration is unnecessary for this coursework.

---

## 6. Evaluation and Decision Rule

### 6.1 TTS quality

Evaluate only dimensions needed for audiobook production:

#### Content and pronunciation

- normalization errors;
- omissions;
- insertions/repetitions;
- substitutions;
- pronunciation errors;
- Vietnamese tone errors where meaningful;
- names/foreign words where relevant.

ASR CER/WER may assist screening but must not be the final correctness judge.

#### Listening quality

ITU-T P.85 Amendment 1 specifically covers subjective evaluation of speech output for audiobook reading tasks. [R8]

For a coursework, use a small relevant subset such as:

- overall impression;
- listening effort;
- pauses;
- intonation;
- acceptance.

#### Long-form robustness

Evaluate passages for:

- skipped or repeated content;
- discontinuities;
- inappropriate pauses;
- severe speaking-rate or prosody instability.

No large separate metric suite is required.

#### Optional character evaluation

Only when character voices are tested:

- speaker-attribution correctness;
- character–voice consistency;
- speaker identification by listeners;
- dialogue comprehension/listening effort.

The question is whether character voices provide enough benefit to justify their added complexity—not whether multiple voices are inherently better.

### 6.2 Publication acceptance

The final EPUB must pass checks for:

- complete required content;
- correct reading order;
- navigation;
- valid text/audio targets;
- synchronization order and coverage;
- required accessible alternatives.

Use:

```text
EPUBCheck
   +
Ace by DAISY
   +
manual accessibility review
   +
manual Media Overlay playback
```

DAISY explicitly notes that Ace cannot establish accessibility by itself; EPUBCheck and manual evaluation are also required. [R9]

### 6.3 Selection rule

#### Stage 1 — Hard gates

A candidate must provide:

- adequate content correctness;
- acceptable pronunciation/intelligibility;
- usable long-form output;
- practical pipeline integration;
- valid accessible EPUB output.

Failure on an accessibility-critical requirement cannot be compensated by better naturalness.

#### Stage 2 — Compare passing candidates

Compare transparently on:

- content/pronunciation accuracy;
- listening quality;
- long-form robustness;
- required manual correction;
- inference practicality.

Do not create an arbitrary weighted aggregate score.

---

## 7. Workflow, Scope, and Research Questions

### 7.1 Workflow

```text
1. Define EPUB/accessibility requirements
               ↓
2. Parse target EPUB
               ↓
3. Analyze target books
               ↓
4. Derive TTS requirements
               ↓
5. Survey + shortlist TTS systems
               ↓
6. Build representative/challenge sets
               ↓
7. Synthesize + evaluate
               ↓
8. One correction loop
               ↓
9. Freeze final configuration
               ↓
10. Final benchmark
               ↓
11. Generate Media Overlays
               ↓
12. EPUBCheck + Ace + manual checks
               ↓
13. Final accessible EPUB 3.3
```

Character processing is inserted only when the optional narration experiment is activated.

### 7.2 Scope

| Status           | Components                                                                                                                                                                                                                                                                                                            |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Must-have**    | EPUB parsing/structure; target-book analysis; text normalization; Vietnamese pronunciation; TTS shortlist; representative/challenge tests; content/listening/long-form evaluation; single narrator; Media Overlays; EPUBCheck; Ace; manual validation                                                                 |
| **Conditional**  | code-switch testing; pronunciation lexicon; complex notation; dialogue-specific analysis; character inventory; speaker attribution; selected character voices; multiple POV narrators                                                                                                                                 |
| **Nice-to-have** | study with blind/print-disabled listeners; larger listening experiment; lightweight character-aware prosody comparison                                                                                                                                                                                                |
| **Out of scope** | TTS training/fine-tuning; full character knowledge graph; automatic age/gender/origin/personality-based voice casting; unique voice for every character; full-cast audio drama; large emotion taxonomy; voice cloning; generated non-verbal acting; streaming/MLOps infrastructure; exhaustive training-data analysis |

A conditional component is added only when **target-book evidence and research value justify its complexity**.

In particular:

> **Character inventory and speaker attribution are not prerequisites for producing the core accessible EPUB.**

### 7.3 Research questions

#### RQ1 — Book requirements

**Which structural and linguistic characteristics of Vietnamese EPUB books materially affect accessible synthetic narration?**

#### RQ2 — TTS capability

**How well do existing Vietnamese-capable TTS systems satisfy the requirements identified from the target books?**

#### RQ3 — End-to-end accessibility

**Can the selected TTS configuration produce a structurally valid, synchronized and practically accessible EPUB 3.3 publication?**

#### Optional RQ4 — Narration strategy

**For dialogue-heavy books, does selected character-voice narration improve speaker identification or listening quality enough to justify speaker-attribution and voice-management complexity compared with a single-narrator baseline?**

RQ4 is activated only if character narration becomes a deliberate experimental objective.

---

## References

**R1 — W3C, EPUB 3.3**
[https://www.w3.org/TR/epub-33/](https://www.w3.org/TR/epub-33/?utm_source=chatgpt.com)

**R2 — W3C, EPUB Accessibility 1.1**
[https://www.w3.org/TR/epub-a11y-11/](https://www.w3.org/TR/epub-a11y-11/?utm_source=chatgpt.com)

**R3 — W3C, EPUB Accessibility specifications (1.1 Recommendation; 1.2 Candidate Recommendation)**
[https://www.w3.org/TR/epub-a11y/all/](https://www.w3.org/TR/epub-a11y/all/?utm_source=chatgpt.com)

**R4 — W3C, EPUB 3 Text-to-Speech Enhancements 1.0**
[https://www.w3.org/TR/epub-tts-10/](https://www.w3.org/TR/epub-tts-10/?utm_source=chatgpt.com)

**R5 — U.S. National Library Service for the Blind and Print Disabled, Narration Specification**
[https://www.loc.gov/nls/who-we-are/guidelines-and-specifications/contract-specifications/narration/](https://www.loc.gov/nls/who-we-are/guidelines-and-specifications/contract-specifications/narration/?utm_source=chatgpt.com)

**R6 — Berthe-Pardo et al., “S-VoCAL: A Dataset and Evaluation Framework for Inferring Speaking Voice Character Attributes in Literature,” LREC 2026**
[https://aclanthology.org/2026.lrec-1.860/](https://aclanthology.org/2026.lrec-1.860/?utm_source=chatgpt.com)

**R7 — Narrative Dialogue Dataset: Speaker and Emotion Annotated Conversational Corpus, Scientific Data, 2026**
[https://www.nature.com/articles/s41597-026-06891-3](https://www.nature.com/articles/s41597-026-06891-3?utm_source=chatgpt.com)

**R8 — ITU-T P.85 Amendment 1, Evaluation of Speech Output for Audiobook Reading Tasks**
[https://www.itu.int/rec/T-REC-P.85/en](https://www.itu.int/rec/T-REC-P.85/en?utm_source=chatgpt.com)

**R9 — DAISY Accessible Publishing Knowledge Base, EPUB Validation Process / Ace**
[https://kb.daisy.org/publishing/docs/epub/validation/overview.html](https://kb.daisy.org/publishing/docs/epub/validation/overview.html?utm_source=chatgpt.com)
[https://kb.daisy.org/publishing/docs/epub/validation/ace.html](https://kb.daisy.org/publishing/docs/epub/validation/ace.html?utm_source=chatgpt.com)
