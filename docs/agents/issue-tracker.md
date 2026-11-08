# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## Implementation tickets after a wayfinder effort

When a wayfinder effort's spec is split into implementation tickets, they go in a sibling directory, not in the map's `issues/`, so the wayfinder frontier never picks them up.

- **Location**: `.scratch/<effort>-impl/issues/<NN>-<slug>.md`, numbered from `01` in dependency order (blockers first). Example: `.scratch/games-advisor-impl/` for `.scratch/games-advisor/`.
- **Header lines**: `Status:`, `Blocked by:`, `Spec:` (links to `../../<effort>/spec.md`, with the sections it implements), `MR:`.
- **Status**: starts as `ready-for-agent` or `ready-for-human`, becomes `resolved` when done. There is no in-progress state.
- **Where the status changes**: `dev` takes no direct pushes (AGENTS.md §8.1). A ticket with an MR is set to `resolved` in its own MR, in the last commit before merge. A ticket without an MR records its result in the first MR that uses it and is resolved there; its `MR:` line names that MR.
- **Skills**: pass the directory path (for example `.scratch/games-advisor-impl/`) to skills that read or write tickets.
