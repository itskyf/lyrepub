# LyrePub

A research coursework project for producing standards-conformant, accessible EPUB publications with synchronized Vietnamese audio.

LyrePub investigates two audio pathways:

1. **TTS synthesis** — generate narration from EPUB text using existing Vietnamese-capable TTS systems.
2. **Audiobook alignment** — align an existing long-form audiobook with the corresponding EPUB content.

Both pathways converge on EPUB Media Overlays and final publication validation while retaining pathway-specific processing where appropriate. The project uses existing models and tools rather than training or fine-tuning speech models.

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

The canonical research questions, methodology, experimental procedure, evaluation criteria, and scope are defined in [`docs/research/protocol.md`](docs/research/protocol.md).

## Publication Target

The primary artifact targets:

- EPUB 3.3;
- EPUB Accessibility 1.1;
- applicable EPUB Accessibility Techniques 1.1;
- synchronized audio through native EPUB Media Overlays.

Outputs are validated with EPUBCheck, Ace by DAISY, and focused manual inspection where automated validation is insufficient.

The coursework also requires a DAISY 3 deliverable generated from the completed EPUB using a standard conversion workflow.

## Development

The project uses [Pixi](https://pixi.prefix.dev/) for reproducible environments and system dependencies. Python package dependencies remain in standard `pyproject.toml` metadata so the package can also be installed in environments without Pixi.

```shell
pixi install
```

Add Python dependencies through PyPI so they remain standard package dependencies:

```shell
pixi add --pypi <package>
pixi add --pypi --feature dev <package>
```

Use regular `pixi add <package>` for system or Conda dependencies such as `ffmpeg`.

Development CLI tools are managed with [mise](https://mise.jdx.dev/) and repository checks with [hk](https://hk.jdx.dev/):

```shell
mise install
hk check
hk fix
hk run pre-commit
```

Agent packages declared in `apm.yml` are installed with [APM](https://microsoft.github.io/apm/):

```shell
apm install
```

## Containers

### audio.cpp

The Compose provider is managed with mise. Podman and NVIDIA CDI remain host prerequisites.

```shell
mkdir --parents data/models
podman compose build audiocpp model-manager
podman compose run --rm model-manager list --remote
podman compose run --rm model-manager install <package-id> --models-dir /app/models
podman compose up audiocpp
```

The WebUI is available at `http://127.0.0.1:8080`.
The server configuration in `containers/audiocpp.json` loads the publication checkpoint and Quỳnh Anh assets from `data/models/VieNeu-TTS-v3-Turbo-GGUF/`.

### Validators

EPUBCheck and Ace are available as Compose tools:

```shell
podman compose build epubcheck ace
```

### Browser validation

The Compose Playwright service provides Chromium for the mise-managed `playwright-cli` without installing a browser on the host:

```shell
podman compose up --detach playwright
```

Use the CLI's remote configuration with `browser.isolated` set to `true` and `browser.remoteEndpoint` set to `ws://127.0.0.1:3000/?browser=chromium`.
The pinned CLI uses the compatible Playwright 1.63 client; the service runs Playwright 1.63.0.
See [publication validation](docs/research/publication-validation.md) for the import and playback workflow.

## Repository Map

- `docs/research/protocol.md`: Canonical research scope, questions, methodology, experiments, and evaluation
- `docs/report/`: Scientific report and interpretation of results
- `src/`: Reusable implementation
- `pyproject.toml`: Python package metadata and Python dependencies
- `mise.toml`: Development-tool versions and installation
- `hk.pkl`: Repository formatting, linting, and validation checks
- GitHub Issues: Scoped research, implementation, experiment, and decision work
- GitHub Milestones: Groups of work contributing to meaningful research or deliverable outcomes
- Pull Requests: Review boundary for repository changes and verification

Live work status, ownership, dependencies, and milestone progress belong on GitHub rather than in repository documentation.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the collaboration and GitHub workflow.

Coding agents should additionally follow [`AGENTS.md`](AGENTS.md).
