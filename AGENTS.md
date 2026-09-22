# AGENTS.md

Repository-wide instructions for coding agents.

## Operating Context

- Use `README.md` for the repository's source-of-truth map and `CONTRIBUTING.md` for the development workflow.
- Treat GitHub Issues and Pull Requests as live work state; do not copy temporary progress, planning, or status into repository documentation.
- Do not create parallel planning, status, decision, or scratch files unless explicitly requested.
- When an Issue exists, keep implementation within its scope. Handle blockers, scope changes, and durable decisions through the workflow in `CONTRIBUTING.md`.
- Do not commit or push until the implementation gate in CONTRIBUTING.md is satisfied.

## Implementation

### Code Style

- Implement only what the current requirement needs; avoid speculative abstraction, configurability, or extensibility.
- Keep logic local unless extracting it clearly reduces duplication or complexity.
- Follow the repository's existing formatter, linter, type-checker, naming conventions, and project structure.
- Reuse existing project patterns before introducing new frameworks or dependencies.
- Do not perform unrelated refactoring while implementing a task.
- Do not silently change externally consumed schemas or persisted output formats.

### Research-Sensitive Changes

- Do not change research questions, EDA categories, benchmark sampling rules, evaluation metrics, acceptance criteria, or other methodological definitions as an implementation detail.
- If implementation reveals that such a change is necessary, treat it as a methodological decision and follow the Decision workflow in `CONTRIBUTING.md` before making the new behavior canonical.
- Preserve only the traceability needed to support the research method and interpret results; do not add lineage or provenance mechanisms unless explicitly required.
- Do not modify experimental data, benchmark expectations, or expected results merely to make a test or evaluation pass.

### Testing and Validation

- Validate changes using the smallest relevant check that provides meaningful confidence in correctness.
- Use existing tests, targeted runs, sanity checks, known examples, or research evaluation as appropriate.
- Do not add new automated tests unless the task explicitly requires them.
- Do not change research data, benchmark expectations, or methodological criteria merely to make validation pass.

### Error Handling and Logging

- Catch exceptions only when the code can recover, add useful context, or intentionally translate the failure. Catch the narrowest practical exception and preserve the original cause when translating it.
- Prefer built-in exceptions unless callers genuinely need a project-specific failure type.
- Make exception messages factual and specific: describe the failed operation and useful context without speculating about the cause.
- Use the project's existing logging approach for runtime output; do not use `print` or introduce a separate logging framework.
- Log useful milestones and diagnostic context, not routine implementation detail. Avoid logging the same failure repeatedly at multiple layers.

### Code Comments and Docstrings

- Use comments to explain non-obvious reasoning, assumptions, invariants, methodological constraints, or edge cases—not to narrate what the code already states.
- Keep comments concise, factual, and direct. Avoid conversational narration, change history, or temporary reasoning that belongs in an Issue or PR.
- Add docstrings to public, non-trivial, or otherwise non-obvious interfaces. Do not add docstrings to trivial helpers merely for completeness.
- Write docstring summaries as direct imperative descriptions of behavior.
- Document arguments, return semantics, side effects, exceptions, or constraints when they are relevant and not already clear from the interface.
