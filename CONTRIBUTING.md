# Contributing

LyrePub is a small research coursework project. Keep collaboration reproducible, reviewable, and lightweight.

## Work Model

Repository work follows:

```text
Issue → Pull Request → Merge
```

Use GitHub's native work-management features rather than maintaining parallel planning systems.

Each primitive has one purpose:

- **Milestone** — research phase or deliverable outcome.
- **Issue** — a scoped unit of research, implementation, experiment, or decision work.
- **Sub-issue** — decomposition of a larger Goal into independently completable work.
- **Dependency** — a real blocking relationship between Issues.
- **Assignee** — current ownership.
- **Label** — classification when repeated filtering is useful.
- **Pull Request** — reviewable changes to code, configuration, or durable documentation.

Do not duplicate status, phase, priority, or dependency information in labels or documentation. Do not introduce a Project board, custom workflow state, or additional planning system unless the project develops a concrete recurring need for one.

Use milestone due dates only for actual deadlines.

## Issues

Use an Issue before substantive implementation or experimental work.

A sufficiently scoped Issue should make the following clear when relevant:

- context or question;
- scope and explicit non-scope;
- expected output or evidence;
- acceptance criteria.

Use three conceptual Issue roles:

- **Goal** — a larger research or delivery outcome;
- **Task** — an executable unit of work;
- **Decision** — an unresolved methodological or consequential technical choice.

These roles do not require dedicated labels. Use native parent/sub-issue and dependency relationships where they represent real relationships.

Small typo or formatting corrections do not require an Issue.

### Starting Work

Before substantive work:

1. understand the Issue and relevant parent Goal;
2. confirm that required dependencies are resolved;
3. establish ownership;
4. read the repository documentation relevant to the task.

Begin implementation when scope and acceptance criteria are sufficiently clear to determine whether the work is complete.

## Research Decisions

The current research method is defined in [`docs/research/protocol.md`](docs/research/protocol.md).

Changes that materially alter research questions, experimental pathways, benchmark construction, evaluation methods, metrics, or acceptance criteria are research decisions rather than implementation details.

For such a change:

1. discuss alternatives and evidence in a Decision Issue;
2. record the accepted method in the relevant durable documentation, configuration, or code through a Pull Request;
3. merge the change;
4. close the Decision Issue.

The closed Issue preserves the rationale. The repository preserves the current method.

Ordinary implementation choices that do not change the research method belong in the implementation Issue or Pull Request and do not require a separate decision process.

## During Work

Keep the Issue body as the current work contract, not a chronological log.

If scope materially changes, update the Issue and leave a concise comment explaining why.

If independent follow-up work is discovered, create a separate Issue and connect it using the appropriate native GitHub relationship.

Use Issue comments for matters outside the code diff, such as:

- scope;
- methodology;
- experimental evidence;
- blockers;
- handoff information.

Use Pull Request review comments for findings about the proposed diff.

Do not create parallel `plan.md`, `status.md`, research-log, or ADR systems without a demonstrated need.

## Pull Requests

Prefer one coherent concern per Pull Request.

A Pull Request should state:

- what changed;
- how it was verified;
- any effect on research methodology or reproducibility;
- the Issue it completes, using `Closes #N` when the entire Issue is satisfied.

Use draft Pull Requests when early review is useful. Mark a Pull Request ready when its acceptance criteria and relevant verification are complete.

Merge is the point at which a repository change becomes canonical.

## Development Tooling

Development tools are managed by [mise](https://mise.jdx.dev/getting-started.html) in `mise.toml`; linting and formatting are configured by [hk](https://hk.jdx.dev/getting_started.html) in `hk.pkl` (text-based configuration).

```shell
mise install
hk check --all
hk run pre-commit
```

Use `hk fix --all` when applying supported automatic fixes.

## Research Reproducibility

Use the smallest relevant checks that provide meaningful evidence that a change works.

Depending on the work, reproducibility may require recording:

- source code;
- dependency lockfiles;
- model or tool version;
- inference configuration;
- preprocessing and evaluation procedure;
- stable identifiers or checksums for external inputs;
- scripts or commands needed to reproduce reported results.

Do not create a general-purpose provenance or data-lineage system for information that can be reproduced adequately through normal project files and experiment artifacts.

Do not commit unnecessary large generated files, raw datasets, model checkpoints, or audiobook assets. Prefer reproducible generation or externally managed inputs when appropriate.

Research data, expected outputs, methodological criteria, or evaluation thresholds must not be changed merely to make an implementation or experiment pass.
