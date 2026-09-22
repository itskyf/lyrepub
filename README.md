# Vietnamese Accessible EPUB TTS

A coursework project for converting Vietnamese EPUB publications into EPUB 3.3 publications with synchronized synthetic narration through Media Overlays.

The project evaluates and integrates existing TTS systems; it does not train a new TTS model.

## Goals and Scope

The project studies three questions:

1. Which structural and linguistic properties of Vietnamese EPUB books create material requirements for TTS?
2. How well do existing Vietnamese-capable TTS systems satisfy those requirements?
3. Can the selected system be integrated into a valid, synchronized, and accessible EPUB 3.3 pipeline?

The core workflow is:

```text
EPUB
→ text and structure analysis
→ TTS requirements
→ benchmark
→ TTS evaluation
→ audio alignment
→ Media Overlays
→ EPUB validation
```

Training, voice cloning, real-time serving, MLOps, and expressive audio effects are outside the default scope.

## Repository Map

| Location                    | Purpose                                                                                              |
| --------------------------- | ---------------------------------------------------------------------------------------------------- |
| `docs/research/protocol.md` | Canonical research questions, scope, methodology, benchmark rules, and evaluation protocol           |
| `docs/report/`              | Final scientific narrative: methods actually used, results, discussion, limitations, and conclusions |
| `src/`                      | Reusable implementation                                                                              |
| GitHub Issues & Milestones  | Current project phases, goals, tasks, decisions, dependencies, blockers, and handoffs                |
| Pull Requests               | Review boundary for changes to code, configuration, and durable documentation                        |

Live project status belongs on GitHub, not in repository documentation.

## Working on the Project

For contribution and GitHub workflow rules, read [CONTRIBUTING.md](CONTRIBUTING.md).

Coding agents must also follow [AGENTS.md](AGENTS.md).

Use repository-relative links when adding documentation so that links remain valid across branches and local clones.
