# Contributing

This is a coursework repository. Keep the workflow traceable and lightweight.

## Development Workflow

Before starting substantive work:

1. read the Issue and its parent Goal, if any;
2. verify that blocking Issues are resolved;
3. assign yourself or otherwise establish ownership;
4. read the relevant repository documentation and existing implementation.

**Implementation gate:** Begin implementation only when the Issue has clear acceptance criteria, blockers are resolved, ownership is assigned, and no open Decision Issue affects it.

Keep changes scoped to the Issue.

If new independent work is discovered, create a separate Issue and connect it using the appropriate GitHub relationship.

## Issues and Decisions

### When to Use an Issue

Create or use an Issue for substantive:

- implementation work;
- experiments;
- research-method changes;
- design decisions;
- discovered follow-up work.

A trivial typo or formatting correction may be submitted directly as a Pull Request.

### Issue Roles

Use three conceptual roles:

- **Goal** — a larger outcome consisting of several pieces of work.
- **Task** — an executable unit of work.
- **Decision** — an unresolved methodological or technical choice.

Use GitHub's native parent/sub-issue and blocking relationships rather than encoding dependencies only in prose.

### Tracking

- Use milestones for project phases or deliverables.
- Use labels only to classify work; prefer GitHub's default labels.
- Use parent/sub-issue relationships for Goal → Task decomposition and issue dependencies for blockers.
- Do not duplicate phase, status, or dependency information in labels.

### Decision Lifecycle

Keep alternatives, evidence, and unresolved reasoning in the Decision Issue while the decision is open.

Once a decision becomes durable:

1. update the relevant repository documentation, code, or configuration through a Pull Request;
2. merge the change;
3. close the Decision Issue.

The closed Issue remains the rationale and decision history. The repository contains the current decision.

Do not create parallel `plan.md`, `status.md`, scratch documentation, Wiki pages, or ADRs unless the project develops a concrete need for them.

## During Work

Update the Issue only when shared state materially changes, such as when a blocker is discovered, scope changes, a decision is required, or independent follow-up work is found.

If work stops before completion, leave a concise handoff describing what is done, what remains, and any blocker or open question.

## Pull Requests

A Pull Request is the review boundary for completed work. Use draft PRs for early feedback; mark ready only after satisfying acceptance criteria and verification.
Each PR should contain:

- a concise summary;
- verification performed;
- any effect on research methodology or reproducibility;
- `Closes #N` for the primary implementation Issue when appropriate.

Prefer one coherent concern per PR.

An implementation session or commit does not make an Issue complete. Completion follows review and merge.

## Research and Documentation Changes

Do not rewrite methodology merely to fit observed results.

A change to research questions, EDA definitions, benchmark construction, metrics, or acceptance criteria should first be treated as an explicit research decision.

Scientific observations belong in Results. Their interpretation, threats to validity, rejected hypotheses, and limitations belong in the final report's Discussion and Limitations sections.

Live progress and temporary reasoning belong on GitHub rather than in durable research documentation.

## Verification

Before opening a PR:

- validate the change using the smallest relevant check that provides meaningful confidence in correctness;
- report the validation performed in the PR;
- ensure generated results remain reproducible from committed code and configuration;
- avoid committing unnecessary generated or large binary artifacts.
