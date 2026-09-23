# Contributing

LyrePub is a small research coursework project. Keep collaboration reproducible, reviewable, and lightweight.

## Work Model

Repository work follows:

```text
Issue → Pull Request → Merge
```

Use GitHub's native work-management features rather than maintaining parallel planning systems.

Each primitive has one purpose:

- **Milestone** — groups work contributing to a meaningful research or deliverable outcome. It is not a sprint or workflow status.
- **Issue** — an independently trackable unit of work or decision.
- **Sub-issue** — decomposes a parent Issue only when separate implementation, ownership, review, or completion is useful.
- **Dependency** — represents a real blocking relationship between Issues.
- **Assignee** — identifies current ownership.
- **Label** — classifies work when repeated filtering is useful.
- **Pull Request** — reviews concrete changes to code, configuration, or durable documentation.

Do not create an Issue merely to mirror a Milestone.

Do not duplicate status, milestone, ownership, priority, parent-child, or dependency information in Issue bodies, labels, or repository documentation when GitHub already represents it natively.

Do not introduce a Project board, custom workflow state, or additional planning system without a demonstrated recurring need.

Use milestone due dates only for actual deadlines.

## Issues

Use an Issue before substantive implementation, experimental work, or a consequential decision that needs independent tracking.

An Issue should provide enough information to establish:

- why the work or decision is needed;
- what is in scope;
- observable outputs, evidence, or acceptance criteria that determine completion.

State explicit non-scope only when it prevents meaningful ambiguity.

Use the repository Issue template when creating normal work items. The template provides the current presentation structure; this document defines the workflow semantics.

Use GitHub metadata and native relationships for assignees, milestones, sub-issues, and dependencies rather than repeating them in the Issue body.

Create sub-issues only when decomposition provides practical value, such as independent ownership, review, or completion. Do not create hierarchies for work that can be completed coherently in one Issue.

Small typo or formatting corrections do not require an Issue.

## Work Lifecycle

Work generally follows:

```text
Frame → Execute ↔ Inspect → Close
```

- **Frame:** establish sufficient scope, evidence requirements, and completion criteria.
- **Execute:** implement, run experiments, or gather the required evidence.
- **Inspect:** review outputs, representative cases, failures, measurements, and relevant repository changes.
- **Close:** merge required repository changes and close the Issue when its completion criteria are satisfied.

Execution and inspection may repeat as necessary.

A separate decision step is not required for ordinary implementation choices. When work exposes a consequential methodological choice, resolve it using the research-decision process below.

Work may proceed in parallel whenever no real dependency blocks it.

## Research Decisions

The current research method is defined in [`docs/research/protocol.md`](docs/research/protocol.md).

Changes that materially alter research questions, experimental pathways, benchmark construction, evaluation methods, metrics, human-assistance conditions, or acceptance criteria are research decisions rather than implementation details.

When such a decision requires independent tracking:

1. discuss the alternatives and relevant evidence in an Issue;
2. record the accepted method in the appropriate durable documentation, configuration, or code through a Pull Request;
3. merge the change;
4. close the Issue.

Do not create a separate decision-tracking Issue when the current Issue already exists specifically to resolve that decision.

The closed Issue preserves discussion and rationale. The repository preserves the current method.

Ordinary implementation choices that do not change the research method belong in the implementation Issue or Pull Request.

## During Work

Keep the Issue body as the current work contract, not a chronological log.

If scope materially changes, update the Issue body and leave a concise comment explaining the change.

If independent follow-up work is discovered, create another Issue only when it needs separate tracking. Use a sub-issue or dependency relationship when that relationship is real.

Use Issue comments for matters outside the proposed diff, such as:

- scope or methodological discussion;
- experimental evidence;
- blockers;
- significant findings or handoff information.

Use Pull Request review comments for findings about the proposed diff.

Do not create parallel `plan.md`, `status.md`, research-log, ADR, or similar tracking systems without a demonstrated need.

## Pull Requests

Prefer one coherent concern per Pull Request.

Use the repository Pull Request template. A Pull Request should make clear:

- what changed and why;
- how the change was verified;
- any effect on research methodology or reproducibility;
- the related Issue, when applicable.

Use `Closes #N` only when merging the Pull Request fully completes that Issue. Otherwise, reference the Issue without a closing keyword.

Use draft Pull Requests when early review is useful. Mark a Pull Request ready when the relevant work and verification are complete.

Merge is the point at which repository changes become canonical.

## Research Reproducibility

Record only the information and artifacts needed to reproduce reported work.

Depending on the experiment or implementation, this may include:

- source code;
- dependency lockfiles;
- model, checkpoint, or tool version;
- inference settings that materially affect results;
- preprocessing and evaluation procedures;
- stable identifiers or checksums for external inputs when useful;
- commands or scripts needed to reproduce reported results;
- intermediate outputs required to reproduce measurements or serve as inputs to later pipeline stages.

Use the simplest appropriate machine-readable representation for persisted intermediate data. Do not require a manifest or provenance file when ordinary project files, configuration, commands, and artifacts already provide sufficient reproducibility.

Do not build a general-purpose provenance or data-lineage system.

Do not commit unnecessary large generated files, raw datasets, model checkpoints, or audiobook assets. Prefer reproducible generation or externally managed inputs when appropriate.

Research data, expected outputs, methodological criteria, or evaluation thresholds must not be changed merely to make an implementation or experiment pass.

## Development Tooling

See [`README.md`](README.md) for environment setup and local usage.

Run repository checks with:

```shell
hk check --all
hk run pre-commit
```

Use `hk fix --all` when applying supported automatic fixes.
