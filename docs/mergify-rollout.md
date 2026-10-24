# Mergify org rollout runbook

Target state: **Mergify merges every approved green PR in every ACTIVE repo; nobody
clicks merge.** A repo is ACTIVE when its default branch has a commit in the last
30 days.

The org policy lives in this repository's `.mergify.yml`. It is a port of the merge
queue that already runs green in the org's reference monorepo, adapted for
inheritance, plus a Dependabot fast lane. This runbook is the procedure the
conductor executes per repo.

**Neutrality rule for this file and the org policy:** this repository is public.
Never write private repository names, internal ruleset IDs, hostnames, runner names,
or internal PR numbers into it. Reference private repos as "the reference monorepo"
or `<repo>` and keep concrete check names in the private repos' own configs.

## Architecture

- Every participating repo gets a `.mergify.yml` whose first key is `extends: .github`
  (the repo name in this org, no owner prefix). Mergify requires the app to be
  installed on this `.github` repository as well as the extending repo.
- Mergify merges configuration from the org policy with the repo's local file:
  - `defaults`, `merge_queue`, `merge_protections_settings`: merged key by key;
    local values win.
  - `pull_request_rules`, `queue_rules`, `priority_rules`, `merge_protections`:
    merged **by rule name** — a local rule with the same name replaces the org rule;
    every org rule not redeclared locally applies as-is.
  - `shared` (YAML anchors) and `scopes`: never inherited. A repo that wants anchors
    defines its own.
- Routing is fixed by the org policy: the unnamed `queue` action sends a PR to the
  first queue rule whose `queue_conditions` match, in order:
  `deploy-fix` → `dependabot` → `default` → `merge-commit`.

### Queue rules the org policy defines (override targets)

| Queue rule | Entry conditions (beyond the common gate) | Merge method / batching |
|---|---|---|
| `deploy-fix` | `label = deploy-fix` | squash, batch 1, priority high with checks interruption |
| `dependabot` | Dependabot author AND `dependabot-update-type != version-update:semver-major` | squash, batch 1–5, 15 min batch wait, **no review gate** |
| `default` | everything else that passes the review gate | squash, batch 1–4, 5 min batch wait |
| `merge-commit` | `label = queue/merge-commit` | merge commit, batch 1 (subtree/reformat/history PRs) |

Labels with fixed meaning: `deploy-fix` (emergency lane), `queue/merge-commit`
(land unsquashed), `hold` (keep out of main).

Dependabot majors fail the `dependabot-update-type != version-update:semver-major`
condition, miss the `dependabot` queue, and fall through to `default`, which
requires review. Patch and minor updates queue and merge with no human review once
CI is green; the org policy's `approve dependabot patch and minor updates` rule
supplies the bot approval that approval-requiring rulesets demand.

## Per-repo procedure (ACTIVE repos only)

For each repo from the conductor's authenticated sweep, in inventory-table order:

1. **Read the check names. Never guess.** Open the repo's latest PR run against the
   default branch and copy the exact check-run names (`job name / step or matrix
   leg`, e.g. `checks / check`). The sweep supplies this list; if the latest run is
   stale or ambiguous, trigger a run and read it again. A condition naming a check
   that does not exist keeps every PR out of the queue — fail-safe, but stuck.
2. **Write the repo's `.mergify.yml`** from the template below, substituting:
   - `<DEFAULT_BRANCH>` — the repo's default branch (`main` unless the sweep says
     otherwise; the org policy's rules say `base = main`, so a non-`main` default
     branch means overriding every rule that mentions it);
   - `<CHECK_N>` — the exact check names from step 1, one `check-success` line per
     required check of the repo's default-branch ruleset, in both `queue_conditions`
     and `merge_conditions`.
   Override all four queue rules — they all reference check names. Keep the rule
   names identical to the org policy's; the name is the override key. If the repo's
   review authority differs from the org's Kiro gate, also replace the
   `approved-reviews-by` line.
3. **Add `dependabot.yml`** from the template below if the repo has no Dependabot
   config; if it has one, align its schedule and grouping with the template.
4. **Open the rollout PR** (branch `ci/mergify-rollout`, conventional title, e.g.
   `ci(mergify): adopt the org merge queue`). The Mergify config check on the PR
   must pass — a config error there blocks everything downstream.
5. **Require `Mergify Merge Protections`** in the repo's default-branch ruleset
   (or branch protection) so button-click merges are also blocked. Zero manual
   merges means the queue is the only merge path.
6. **Dry-run one PR**: label an existing green PR `deploy-fix`-free, confirm it
   enters `default`, CI runs on the queue draft, and it merges. Then leave the rest
   to the queue.

### Per-repo `.mergify.yml` template

```yaml
# yaml-language-server: $schema=https://docs.mergify.com/mergify-configuration-schema.json
extends: .github
#
# Local overrides of the org policy (systemfsoftware/.github). Rule lists merge BY
# NAME with the org policy; the four queue rules below replace the org's because
# they carry THIS repo's real check names, read from this repo's latest PR run.
#
# Common gates are restated literally: the org policy's `shared` anchors are never
# inherited, so this file cannot reference them.

shared:
  ci_checks: &ci_checks
    - check-success = <CHECK_1>
    - check-success = <CHECK_2>
  review_gate: &review_gate
    - approved-reviews-by = kiro-systemf[bot]
    - "#changes-requested-reviews-by = 0"

queue_rules:
  - name: deploy-fix
    merge_method: squash
    batch_size: 1
    max_checks_retries: 1
    checks_timeout: 60 min
    commit_message_format:
      title: pr-title
      body: pr-body
    queue_conditions:
      - base = <DEFAULT_BRANCH>
      - -draft
      - label = deploy-fix
      - -label = queue/merge-commit
      - -label = hold
      - and: *review_gate
      - and: *ci_checks
    merge_conditions:
      - and: *ci_checks

  - name: dependabot
    merge_method: squash
    batch_size:
      min: 1
      max: 5
    batch_max_wait_time: 15 min
    batch_max_failure_resolution_attempts: 2
    max_checks_retries: 1
    checks_timeout: 60 min
    commit_message_format:
      title: pr-title
      body: pr-body
    queue_conditions:
      - base = <DEFAULT_BRANCH>
      - -draft
      - -label = deploy-fix
      - -label = queue/merge-commit
      - -label = hold
      - "author ~= ^(app/dependabot|dependabot\\[bot\\])$"
      - dependabot-update-type != version-update:semver-major
      - and: *ci_checks
    merge_conditions:
      - and: *ci_checks

  - name: default
    merge_method: squash
    batch_size:
      min: 1
      max: 4
    batch_max_wait_time: 5 min
    batch_max_failure_resolution_attempts: 2
    max_checks_retries: 1
    checks_timeout: 60 min
    commit_message_format:
      title: pr-title
      body: pr-body
    queue_conditions:
      - base = <DEFAULT_BRANCH>
      - -draft
      - -label = deploy-fix
      - -label = queue/merge-commit
      - -label = hold
      - and: *review_gate
      - and: *ci_checks
    merge_conditions:
      - and: *ci_checks

  - name: merge-commit
    merge_method: merge
    batch_size: 1
    max_checks_retries: 1
    checks_timeout: 60 min
    commit_message_format:
      title: pr-title
      body: pr-body
    queue_conditions:
      - base = <DEFAULT_BRANCH>
      - -draft
      - label = queue/merge-commit
      - -label = hold
      - and: *review_gate
      - and: *ci_checks
    merge_conditions:
      - and: *ci_checks
```

Omitted keys are inherited: `merge_queue`, `defaults`, `priority_rules`,
`merge_protections`, `merge_protections_settings`, `commands_restrictions`, and the
`queue when ready` / `approve dependabot patch and minor updates`
`pull_request_rules`. A repo whose routing base differs overrides the inherited
`queue when ready` rule (same name) with `base = <DEFAULT_BRANCH>` conditions.

### `dependabot.yml` weekly grouping template

```yaml
version: 2
updates:
  # One block per ecosystem the repo actually uses; delete the rest.
  - package-ecosystem: npm
    directory: "/"
    schedule:
      interval: weekly
    # The Mergify queue rebases and batches; Dependabot must not rebase on every push.
    rebase-strategy: "disabled"
    commit-message:
      prefix: "chore(deps)"
    groups:
      patch-and-minor:
        applies-to: version-updates
        update-types:
          - patch
          - minor
    # Major updates stay ungrouped: they must be reviewed one by one.
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
    rebase-strategy: "disabled"
    commit-message:
      prefix: "chore(deps)"
    groups:
      patch-and-minor:
        applies-to: version-updates
        update-types:
          - patch
          - minor
```

## INACTIVE repos (no default-branch commit in 30 days)

Do not extend the org policy. For each INACTIVE repo with a dangling rollout PR from
the 2026-10-18 wave:

1. Close the PR with a comment: "Repo inactive (no default-branch commit in 30
   days); the org Mergify policy is not being rolled out here. Reopen activity by
   pushing to the default branch and following docs/mergify-rollout.md in the org
   `.github` repository."
2. Delete the pushed policy branch.
3. Leave any pre-existing repo-local `.mergify.yml` untouched — it predates this
   rollout and belongs to the repo's owners.

## Inventory

The conductor's authenticated sweep fills one row per repo. Columns:

| Column | Source |
|---|---|
| repo | org repo name |
| visibility | public / private |
| default branch | repo settings |
| last default-branch commit (UTC) | `GET /repos/{owner}/{repo}/commits/{default_branch}` |
| ACTIVE (≤30 days) | derived |
| open PRs | `GET /repos/{owner}/{repo}` `open_issues_count` minus open issues, or the PR list |
| Dependabot PRs | PR list filtered by author |
| current .mergify.yml | default-branch file list |
| checks on latest PR run | latest completed PR check-runs — exact names, never guessed |
| action | extend / close (INACTIVE) / already-conformant |
| rollout branch + PR | created in step 4 |
| status | pending / config-check green / dry-run merged / closed |

## Verification checklist (per repo, after the rollout PR is open)

- [ ] Mergify config check passes on the rollout PR itself.
- [ ] Every condition check name exists verbatim on the repo's latest PR run.
- [ ] `Mergify Merge Protections` is a required check in the default-branch ruleset.
- [ ] One green PR rode the `default` queue end to end (draft CI → squash merge).
- [ ] One Dependabot patch/minor PR rode the `dependabot` queue with no human review.
- [ ] A Dependabot major PR stayed out of `dependabot` and waits on `default` for review.

## Known hazards

- **Stale check names**: the 2026-10-18 rollout wave named checks that some repos no
  longer run; those PRs never queue anything. Re-read check names per repo at
  override time; do not resurrect old names.
- **Anchors don't inherit**: a repo extending `.github` that references the org
  policy's anchors produces an invalid YAML/undefined-alias error. Restate
  conditions literally, as the template does.
- **Approval-requiring rulesets** would block the Dependabot fast lane; the org
  policy's auto-approve rule satisfies them. If a repo overrules that locally, its
  Dependabot patch/minor PRs need review again — say so in the repo's PR body.
- **Two config files**: Mergify refuses to evaluate a PR that leaves two of
  `.mergify.yml`, `.mergify.yaml`, `.mergify/config.yml`, `.mergify/config.yaml`,
  `.github/mergify.yml`, `.github/mergify.yaml` in place. Keep exactly one.
