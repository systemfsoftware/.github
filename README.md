# systemfsoftware/.github

Org-wide defaults. The shared Mergify merge policy lives in `.mergify.yml`; every repo extends it.

## Subtree PRs

Subtree PRs (`git subtree add` / `git subtree pull`) merge with a merge commit, never a squash (ruling 9). Repos that merge through Mergify implement the `subtree`-queue convention documented in `.mergify.yml` (under `defaults`), and the org-level "Subtree claim needs subtree history" protection reports PRs that claim subtree work without carrying the commit trailers. Recognition reads the commits themselves — never a title or label.
