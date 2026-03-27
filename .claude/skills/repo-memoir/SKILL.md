# repo-memoir skill

Generate or update a living repo memoir of a codebase.

## Usage
- "Generate a repo memoir of owner/repo"
- "Update the repo-memoir repo memoir for this repo"
- "What's the story of how this codebase evolved?"
- "Who shaped this codebase most?"

## What it does
Analyzes full git history, clusters commits into narrative chapters,
detects architectural turning points, identifies key contributors,
and generates a readable memoir of the codebase's evolution.

## Execution contract
1. Run `repo-memoir generate --repo <repo>` when no sidecar exists.
2. Run `repo-memoir update --repo <repo>` when sidecar exists.
3. Return output markdown path and top contributors.
