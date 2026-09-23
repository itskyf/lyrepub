# LyrePub

A research coursework project for producing standards-conformant, accessible EPUB publications with synchronized Vietnamese audio.

LyrePub investigates two audio pathways:

1. **TTS synthesis** — generate narration from EPUB text using existing Vietnamese-capable TTS systems.
2. **Audiobook alignment** — align an existing audiobook with the corresponding EPUB content.

Both pathways converge on the same synchronization and publication pipeline. The project uses existing models and tools rather than training or fine-tuning new speech models.

## Pipeline

```text
EPUB
  ↓
preserve structure and extract synchronization targets
  │
  ├── TTS synthesis ────────────────┐
  │                                 │
  └── align with existing audiobook ┤
                                    ↓
                           text–audio timings
                                    ↓
                         EPUB Media Overlays
                                    ↓
                  accessible EPUB 3.3 publication
                                    ↓
                       validation and DAISY 3
```

The exact research questions, experimental methodology, evaluation procedure, and scope are defined in [`docs/research/protocol.md`](docs/research/protocol.md).

## Publication Target

The primary artifact targets:

- EPUB 3.3;
- EPUB Accessibility 1.1;
- applicable EPUB Accessibility Techniques 1.1;
- synchronized audio through native EPUB Media Overlays.

Outputs are validated with EPUBCheck, Ace by DAISY, and focused manual inspection where automated validation is insufficient.

The coursework also requires a DAISY 3 deliverable, generated from the completed publication using a standard conversion workflow.

## Running Locally

LyrePub uses [pixi](https://pixi.prefix.dev/latest/installation/) for reproducible project environments. Install Pixi using its official installation guide, then from the repository root run:

```shell
pixi install
```

Run project commands inside the environment with:

```shell
pixi run <command>
```

## Repository Map

| Location                    | Purpose                                                                       |
| --------------------------- | ----------------------------------------------------------------------------- |
| `docs/research/protocol.md` | Canonical research scope, questions, methodology, experiments, and evaluation |
| `docs/report/`              | Final scientific report and interpretation of results                         |
| `src/`                      | Reusable implementation                                                       |
| `pyproject.toml`            | Python project and reproducible dependency environment                        |
| GitHub Issues               | Scoped research, implementation, experiment, and decision work                |
| GitHub Milestones           | Research phases and deliverable outcomes                                      |
| Pull Requests               | Review boundary for repository changes                                        |

Live project status belongs on GitHub rather than in repository documentation.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the development and GitHub workflow.

Coding agents should additionally follow [`AGENTS.md`](AGENTS.md).
