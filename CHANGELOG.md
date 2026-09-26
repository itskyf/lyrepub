# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-26

### Added

- Add EPUB text parsing and structure extraction (`lyrepub.epub_text`) with paragraph, heading, ruby annotation, and drop-cap handling, supported by unit tests.
- Add sentence segmentation via `wtpsplit` using pinned `sat-3l-sm` checkpoint revision (`lyrepub.segmentation`).
- Add Vietnamese Named Entity Recognition candidate detection using `NlpHUST/ner-vietnamese-electra-base` (`lyrepub.ner`).
- Add frozen inspection cases for sentence boundaries and entity-rich segments derived from source texts (`lyrepub.inspection`).
- Add comprehensive source characterization report (`docs/research/source-characterization.md`) covering text strata, audiobook alignment, EPUB structure, and NLP candidate suitability.
- Add source scanning and structural inspection utilities (`scripts/scan_sources.py`, `scripts/inspect_epub_structure.py`, `scripts/inspect_audiobook.py`, `scripts/inspect_audiobook.sh`).
- Add candidate NLP screening scripts for sentence segmentation and NER evaluation (`scripts/screen_*.py`).
- Add bronze source ingestion and release-download scripts (`scripts/ingest_original_sources.sh`, `scripts/fetch_release_sources.sh`).
- Add `shellharden` and `shfmt` tooling with pre-commit checks.
- Add `google-colab-cli` to dev dependencies and `typst-author` agent skill.

### Changed

- Clarify Issue and Pull Request boundaries in contribution guidelines (`CONTRIBUTING.md`).
- Document `hk check --pr` workflow in contribution guidelines and refine local check commands.
- Pin Python dependency to `>=3.13,<3.14` in Pixi configuration.
- Update text strata categorization and citations in research protocol (`docs/research/protocol.md`).

## [0.2.0] - 2026-09-24

### Added

- Add GitHub work-item issue template for scoped tasks.

### Changed

- Reframe project scope around accessible synchronized EPUBs with dual audio pathways (synthesis and alignment).
- Streamline contribution guidelines, work lifecycle, and agent instructions.
- Simplify pull request template.

### Fixed

- Correct front matter formatting in work-item issue template.

## [0.1.0] - 2026-09-23

### Added

- Bootstrap project layout with Pixi package and environment definitions.
- Integrate initial dependencies for audio/voice processing, e-book parsing, and text processing.
- Add repository guidelines, agent workflows, and contribution documentation.
- Add agent skills for conventional commits, branches, GitHub issues, and release workflows.

[0.3.0]: https://github.com/itskyf/lyrepub/compare/v0.2.0...release/v0.3
[0.2.0]: https://github.com/itskyf/lyrepub/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/itskyf/lyrepub/releases/tag/v0.1.0
