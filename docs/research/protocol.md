# Research Protocol

## 1. Objective

This coursework studies how to produce an accessible EPUB 3.3 publication with synchronized Vietnamese audio.

Two existing-system pathways are evaluated:

1. **TTS:** EPUB text → synthesized narration.
2. **Audiobook alignment:** existing long-form audiobook + EPUB text → synchronized timings.

No speech model is trained or fine-tuned.

Both pathways must ultimately provide a correspondence between publication content and audio timing suitable for synchronized EPUB playback.

The primary authored artifact is a standards-conformant EPUB. DAISY 3 is generated from the completed EPUB for submission.

## 2. Research Questions

### RQ1 — Source requirements

Which properties of the selected EPUBs and, where applicable, their audiobooks materially affect synchronized audio processing?

### RQ2 — Audio processing

How effectively can directly usable existing systems provide synchronized Vietnamese audio through TTS synthesis or existing-audiobook alignment?

### RQ3 — Publication

Can the resulting audio and timings be integrated reproducibly into a valid and accessible EPUB 3.3 publication and converted to the required DAISY 3 deliverable?

## 3. Scope

### In scope

- EPUB structure and text extraction;
- text preprocessing required by the selected books;
- sentence-level or similarly justified synchronization units;
- inference with existing TTS, ASR, and alignment systems;
- long-form audiobook-to-EPUB alignment;
- EPUB Media Overlays;
- EPUBCheck, Ace by DAISY, and focused manual inspection;
- reproducible experiments;
- final DAISY 3 conversion.

### Out of scope

- model training or fine-tuning;
- new speech or alignment architectures;
- character-specific voice systems unless later justified by a separate research question;
- unrelated NLP stages;
- streaming, serving, MLOps, or production infrastructure;
- elaborate data-lineage or provenance systems.

Processing stages are introduced only when justified by the source material, applicable standards, or observed experimental failures.

## 4. Source Characterization and Common Processing

The common processing stage must preserve the publication structure and accessibility semantics required for the final EPUB.

Text preprocessing may derive forms needed for synthesis, recognition, or alignment, but must not unintentionally alter the authored EPUB content evaluated as the final publication.

Before final experiments, characterize only source properties that can materially affect the evaluated pathways, such as:

- document and chapter structure;
- TTS-relevant text strata adapted from complex-text robustness research: ordinary text, number/date expressions, named entities, long text, code-switched or mixed-language text, and punctuation-related structures;
- audiobook track or chapter correspondence;
- inserted, omitted, repeated, or edition-mismatched audiobook content.

Use these observations to construct representative and challenge test cases rather than an exhaustive linguistic profile of the books.
The text strata organize source characterization and do not imply a difficulty ranking or aggregate score.

## 5. Audio Pathways

### 5.1 TTS

A TTS candidate must:

- provide usable Vietnamese synthesis;
- be directly usable through an existing checkpoint, package, API, or equivalent interface;
- require no training or fine-tuning;
- be suitable for offline publication generation.

Candidates should use the same source material and common preprocessing where meaningful.

Evaluation considers properties relevant to audiobook production, including:

- missing, repeated, or substituted content;
- normalization and pronunciation errors;
- intelligibility;
- inappropriate segmentation or pauses;
- long-form failures;
- required manual correction.

ASR-based CER or WER may be used diagnostically but is not treated as the sole measure of synthesis quality.

### 5.2 Existing-audiobook alignment

An alignment candidate must:

- have a usable implementation and pretrained models where required;
- require no training or fine-tuning;
- provide a plausible Vietnamese or multilingual inference path;
- produce timings suitable for publication synchronization.

The preferred evaluation setting uses long-form audio together with corresponding EPUB text.

Two conditions may be studied:

**Automatic:** chapter or text correspondence is inferred from the source files.

**Chapter-assisted:** a researcher may identify or correct audiobook chapter boundaries or chapter-to-EPUB mappings.

Chapter assistance must not include manual sentence alignment or silent repair of system output.

Alignment evaluation considers:

- successful major-section correspondence;
- synchronization coverage;
- unmatched or incorrectly matched content;
- boundary timing error on a manually verified subset;
- long-form drift or failure;
- required human assistance;
- runtime or resource requirements when practically relevant.

If ASR is used, its output must not be silently replaced by reference EPUB text.

Reference EPUB text may be used explicitly when required by a forced-alignment method.

## 6. Benchmark and Experimental Procedure

The benchmark is derived from the selected books and contains:

- **representative material** for normal use;
- **challenge material** based on observed source or pipeline difficulties;
- **end-to-end material** exercising publication synchronization and accessibility.

Do not add challenge categories without evidence from the selected books or observed system behavior.

Before the final comparison, freeze:

- evaluated candidates;
- benchmark items;
- evaluation measures;
- inference settings that materially affect results.

For each evaluated configuration:

1. use the same corresponding source material where comparison is meaningful;
2. apply the recorded preprocessing;
3. run the recorded tool or model version with the reported settings;
4. retain the outputs needed for evaluation;
5. apply the common analysis procedure;
6. record failures and manual interventions without silently correcting them.

Candidate-specific processing is permitted when required by the documented system interface, but must be reported.

Do not reduce the comparison to an arbitrary weighted overall score. Report results transparently across the dimensions relevant to each pathway.

When approaches produce materially similar outcomes, prefer the simpler reproducible solution.

## 7. Publication Validation

The final publication targets:

- EPUB 3.3;
- EPUB Accessibility 1.1;
- applicable EPUB Accessibility Techniques 1.1;
- EPUB Media Overlays where synchronized audio is provided.

Validate the final EPUB using:

```text
EPUBCheck
+ Ace by DAISY
+ focused manual EPUB inspection
+ manual synchronization playback
```

Automated validation alone is not treated as proof of accessibility or synchronization usability.

After EPUB validation, convert the completed publication to DAISY 3 using a standard conversion tool.

The final DAISY submission contains the required generated resources packaged as a ZIP archive together with a separate text file containing the ZIP SHA-256 hash.

## 8. Reproducibility and Reporting

Record enough information to reproduce each reported experiment, including:

- tool or library version or source revision;
- model or checkpoint identifier;
- inference settings that materially affect output;
- preprocessing;
- relevant software environment;
- commands or scripts used.

Preserve the outputs needed to reproduce reported measurements and record failures or manual interventions without silently correcting them.

Results must report failures and limitations as well as successful cases.

Keep observations separate from interpretation:

- measurements belong in **Results**;
- implications, threats to validity, and limitations belong in **Discussion**.

This file is the canonical source for research questions and methodology.

Material changes to research questions, benchmark construction, evaluation measures, pathway definitions, or human-assistance conditions require an explicit methodological decision and repository review.

Implementation choices that do not alter the research method do not require protocol changes.

## References

- ACM SIGSOFT, [Empirical Standards for Software Engineering Research](https://www2.sigsoft.org/EmpiricalStandards/docs/standards)
- IEEE, [Research Reproducibility](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/research-reproducibility/)
- W3C, [EPUB 3.3](https://www.w3.org/TR/epub/)
- W3C, [EPUB Accessibility 1.1](https://www.w3.org/TR/epub-a11y-11/)
- W3C, [EPUB Accessibility Techniques 1.1](https://www.w3.org/TR/epub-a11y-tech-11/)
- T. Zuo et al., ["Complex-Text Robustness Evaluation and Failure Diagnosis for Low-Resource Multilingual Text-to-Speech"](https://arxiv.org/abs/2609.11545), 2026.
