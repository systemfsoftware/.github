# systemfsoftware/.github

Org-wide defaults. The shared Mergify merge policy lives in `.mergify.yml`; every repo extends it.

## Subtree PRs

A subtree PR merges with a merge commit, never a squash or a rebase.

Open it with `git subtree add` or `git subtree pull --squash` (the org convention). Both write `git-subtree-dir` and `git-subtree-split` trailers. A `git subtree pull` without `--squash` writes no trailers, so Mergify cannot recognise it and the PR matches no `subtree` queue: use `--squash`.

### What Mergify can check

Mergify cannot read a commit's parents. Its only history attribute is [`linear-history`](https://docs.mergify.com/configuration/conditions/) (the PR has no merge commit), and the only `commits[*]` fields a condition may use are `author`, `committer`, `commit_message`, `commit_verification_verified`, `date_*` and `email_*` ([data types, "Commit"](https://docs.mergify.com/configuration/data-types/)). It therefore cannot tell a genuine `git subtree` history from text.

Recognition is two tests:

1. One commit message carries both a `git-subtree-dir:` and a `git-subtree-split: <40 hex>` line.
2. The PR history is not linear.

A subtree PR that was rebased or squashed is linear, so it fails test 2 even though the trailer text survives. A hand-built merge commit with forged trailers passes both tests; that selects the merge-commit method, not a squash, and every check and approval still applies.

### What `extends: .github` inherits

Mergify's [sharing documentation](https://docs.mergify.com/configuration/sharing/) says what a repo that extends this one gets. The local file's rules come first in every rule section, before the ones this file adds.

| This file's section | Inherited? | Documentation |
| --- | --- | --- |
| `shared` (the YAML anchors) | No | "Values in the `shared` key will not be merged and shared between local and remote configurations." |
| `scopes` | No | "Values in the `scopes` key will not be merged either: scopes defined in the extended configuration do not apply to the local configuration." |
| `defaults`, `commands_restrictions`, `merge_queue`, `merge_protections_settings` | Yes, unless the local file sets the same value | "will be merged and remote default values will apply to the local configuration, unless the same value already exists in the local configuration." |
| `pull_request_rules`, `queue_rules`, `priority_rules`, `merge_protections` | Yes, merged by rule name | "Rules in the `pull_request_rules`, `queue_rules`, `priority_rules` or `merge_protections` section will be merged ... A rule will not be overwritten by the extended configuration if it has the same name in both the extended and local configuration." |

What follows for subtrees:

- The "Subtree PRs need subtree history" protection is inherited by every consumer.
- `defaults.queue_rule` applies to every consumer queue, so a queue gets `merge_method: squash` unless it sets its own. The `subtree` queue must set `merge_method: merge`.
- The anchors in `shared` are not visible to a consumer, so a consumer copies the conditions below.
- This file declares no `queue_rules`. If one is added, every consumer inherits it after its own queues, and the first matching queue wins, so check each consumer before adding one.

### What enforces the merge method

The `merge_method` of the queue the PR matches. This file declares no queue, so on its own it chooses no merge method: SYS-1246 is enforced in a repo only once that repo's own `queue_rules` follow the convention below. Put `subtree` before `default`; the first queue whose `queue_conditions` match wins, and a PR matching none is not queued.

```yaml
queue_rules:
  - name: subtree
    merge_method: merge          # never squash or rebase; leave update_method unset
    queue_conditions:
      - 'commits[*].commit_message ~= (?ms)\A(?=.*^git-subtree-dir: \S+$)(?=.*^git-subtree-split: [0-9a-f]{40}$)'
      - -linear-history
      # ...the same checks as default
  - name: default
    queue_conditions:
      # ...the repo's checks
      - '-commits[*].commit_message ~= (?m)^git-subtree-dir: \S+$'
      - not:
          and:
            - 'title ~= (?i)(?<![\w.-])(add|pull|update|sync|vendor|vendored|vendoring|refresh|import|bump|upgrade)(?!\.?[\w-])'
            - 'title ~= (?i)(?<![\w.-])subtrees?(?!\.?[\w-])'
            - or:
                - 'added-files ~= ^(vendor|vendored|third[_-]party|external|repos|subtrees?)/'
                - 'modified-files ~= ^(vendor|vendored|third[_-]party|external|repos|subtrees?)/'
      - -added-files ~= ^vendor/        # the repo's declared subtree prefixes
      - -modified-files ~= ^vendor/
```

A removal-only PR under a prefix matches none of the exclusions and squashes as usual. A rebased or squashed subtree PR carries the dir trailer, so `default` refuses it and `subtree` refuses it as linear: it matches no queue.

### What the org protection adds

"Subtree PRs need subtree history" in `.mergify.yml` gives a named failing check. It applies to two kinds of PR:

- A PR whose title has a vendoring verb (`add`, `pull`, `update`, `sync`, `vendor`, `refresh`, `import`, `bump`, `upgrade`) and the word `subtree`, and that adds or modifies a file under `vendor/`, `vendored/`, `third_party/`, `third-party/`, `external/`, `repos/` or `subtree/`. A word inside a hyphenated or dotted name (`git-subtree-utils`, `subtree.ts`) does not count, and a PR that touches no vendoring directory is not a claim, so `fix: update subtree path handling in parser` is an ordinary PR.
- A PR whose commits carry a `git-subtree-dir:` trailer.

It fails unless the two tests above pass. A removal-only PR is not a claim. Mergify will not merge a PR whose active protection fails. Subtree work under a directory not listed above is caught only by the prefixes a repo declares in its `default` queue.

### What stays open

Mergify does not stop a merge made outside it. A user with write access can still squash from the GitHub UI or API. Requiring the `Mergify Merge Protections` check in a ruleset blocks that merge only for PRs where the protection is active.

## Stacked PRs

Build a native GitHub stack with `gh stack`. Land it with `@mergifyio queue` on the top PR. A stack lands in one merge only when the queue rule has no `commit_message_format` or `commit_message_template`, so `defaults.queue_rule` sets none. Each repo's squash default is PR title and PR body, so the squash commit keeps the same title and body.

- Never run `gh stack rebase` or `gh stack sync` after review. Both force-push the branches and drop the approvals.
- Put review fixes in as new commits, then merge each parent branch up into its child.
