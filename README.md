# repo-memoir

[![CI](https://github.com/just-claw-it/repo-memoir/actions/workflows/ci.yml/badge.svg)](https://github.com/just-claw-it/repo-memoir/actions/workflows/ci.yml)

`repo-memoir` is a Python CLI that generates a living narrative memoir of a codebase.
It is not a changelog and not API documentation. It focuses on:

- how a repository evolved over time,
- who shaped it most,
- when structural turning points happened,
- and what the project became compared to what it started as.

The tool supports both full generation and incremental updates, with optional strict evidence-grounding and offline algorithmic mode.

---

## Core capabilities

- Extracts history from:
  - git commits (including file-level change stats),
  - GitHub PRs and issues (for hosted repos),
  - contributor activity signals.
- Clusters commits into narrative chapters.
- Detects turning points (refactors, pivots, dependency shifts, revivals, bursts).
- Scores contributor influence with configurable weights.
- Generates markdown memoir + JSON sidecar metadata.
- Supports incremental updates from `last_commit_sha`.
- Includes observability commands:
  - `inspect`, `chapters`, `diff`, `doctor`.

---

## Installation

### Prerequisites

- Python `3.11+`
- Git (for local repository analysis)

### Install

```bash
pip install -e .
```

Then use:

```bash
repo-memoir --help
```

---

## Quick start

### Generate a memoir

```bash
repo-memoir generate --repo ./local/path
repo-memoir generate --repo owner/repo
```

### Update incrementally

```bash
repo-memoir update --repo ./local/path
```

### Watch mode

```bash
repo-memoir watch --repo ./local/path --interval 3600
```

---

## CLI commands

### Generation and updates

- `generate` - full memoir generation.
- `update` - incremental update using existing sidecar.
- `watch` - polling loop that runs update/generate automatically.

### Analysis and diagnostics

- `inspect` - quick signal report (contributors, turning points, identity signals).
- `chapters` - preview chapter boundaries before full memoir generation.
- `diff` - compare sidecar snapshot against new commits.
- `doctor` - configuration/provider connectivity checks.

### Cache management

- `cache-clear` - clear local GitHub cache directory.

---

## OpenClaw skill integration

This project also ships an OpenClaw skill wrapper in:

- `.claude/skills/repo-memoir/SKILL.md`
- `.claude/skills/repo-memoir/skill.py`

The skill lets you invoke repo memoir workflows from natural-language prompts, for example:

- "Generate a repo memoir of owner/repo"
- "Update the memoir for this repository"
- "Who shaped this codebase most?"
- "What changed in the codebase story recently?"

Under the hood, the skill calls the same CLI workflows (`generate`/`update`) and returns the resulting output path and key highlights.

---

## Important runtime modes

### Strict grounding

Use strict validation for generated prose:

```bash
repo-memoir generate --repo owner/repo --strict-grounding
```

Fail immediately instead of auto-repair:

```bash
repo-memoir generate --repo owner/repo --strict-grounding --strict-grounding-fail-fast
```

### Offline mode

Run without external LLM/GitHub API calls (algorithmic/local mode):

```bash
repo-memoir generate --repo ./local/path --offline
```

Offline mode is explicitly marked in both markdown output and sidecar metadata.

### No-cache mode

Bypass cache for a single run:

```bash
repo-memoir inspect --repo owner/repo --no-cache
```

---

## Output files

By default, output is written to `./memoirs/`:

- `*.memoir.md` - human-readable narrative document.
- `*.memoir.json` - structured sidecar used for incremental updates.

You can override markdown output path:

```bash
repo-memoir generate --repo owner/repo --output ./out/memoir.md
```

---

## Configuration

Copy and customize:

```bash
cp repomemoir.yaml.example repomemoir.yaml
```

Typical config areas:

- `github` token and cache settings,
- `llm` API endpoint/model/retry/cache settings,
- `analysis` thresholds and weights,
- `output` directory/format.

Environment variable expansion is supported for `${...}` values.

---

## Development

### Run tests

```bash
pytest -q
```

### Lint and type check

```bash
ruff check repomemoir tests
mypy repomemoir
```

### CI

GitHub Actions CI (`.github/workflows/ci.yml`) runs:

- tests on Python `3.11`, `3.12`, `3.13`,
- lint checks (`ruff`),
- type checks (`mypy`).

---

## Notes

- For GitHub repos (`owner/repo`), the tool may use GitHub API data for richer identity and contributor analysis.
- For local paths, analysis focuses on local git history and local repository files.
- This project is designed to be iterative: generate once, then keep the memoir living via `update`/`watch`.
