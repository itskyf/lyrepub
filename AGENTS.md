# AGENTS.md

Repository-wide instructions for coding agents working on LyrePub.

Follow [`CONTRIBUTING.md`](CONTRIBUTING.md) for the GitHub workflow, research decisions, verification, and reproducibility requirements. Follow [`docs/research/protocol.md`](docs/research/protocol.md) for the current research scope and methodology.

Consult additional documentation only when it is relevant to the task.

## Implementation

- Implement the smallest clean solution that satisfies the current requirement.
- Keep the project at research-coursework scale; avoid speculative abstractions, configurability, extensibility, or production infrastructure.
- Prefer established libraries, standards, models, and checkpoints over custom implementations when they satisfy the requirement.
- Reuse existing project structure and patterns before introducing new dependencies or frameworks.
- Keep logic local unless extracting it clearly reduces duplication or complexity.
- Do not perform unrelated refactoring.
- Do not introduce workarounds or silent fallbacks that hide failures.
- Do not silently change externally consumed schemas or persisted output formats.

## Research-Sensitive Changes

Do not redefine research methodology as an implementation detail.

If a change would affect the research scope, experimental pathway, benchmark, evaluation method, metric, acceptance criterion, or other methodological choice, follow the research-decision process in `CONTRIBUTING.md` rather than making the change implicitly.

## Linting and Static Analysis

Treat the repository's configured linting, formatting, and static-analysis checks as constraints to satisfy.

- Fix the underlying code when a configured check reports a problem.
- Do not suppress reported violations with `# noqa`, inline ignores, exclusions, per-file ignores, or equivalent mechanisms.
- Do not modify linting, formatting, static-analysis, or hook configuration to make unrelated code pass.
- Change tooling rules or configuration only when the current Issue explicitly requires a tooling/configuration change.
- If a configured check appears incorrect or incompatible with the required implementation, report the conflict instead of bypassing it.

## Code Comments and Docstrings

Use comments and docstrings only when they add information that is not already clear from the code.

- Explain non-obvious reasoning, assumptions, invariants, methodological constraints, or edge cases.
- Do not narrate control flow or restate the implementation as numbered steps.
- Keep comments concise, factual, and current; do not include conversational reasoning, change history, or temporary notes.
- Add docstrings to public, non-trivial, or otherwise non-obvious interfaces; do not add them to trivial helpers merely for completeness.
- Keep docstring summaries concise and direct.
- Document arguments, return behavior, side effects, exceptions, or constraints only when they are relevant and not already evident from the interface.
