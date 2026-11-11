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

### What enforces the merge method

The `merge_method` of the queue the PR matches. This repo declares no queue, so on its own it enforces nothing: each repo that merges through Mergify declares its own `queue_rules` (they are not inherited, and a queue has no inheritance of its own, so copy the conditions). Put `subtree` before `default`; the first queue whose `queue_conditions` match wins, and a PR matching none is not queued.

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
            - 'title ~= (?i)\b(add|pull|update|sync|vendor|refresh|import|bump|upgrade)\b.*\bsubtrees?\b|\bsubtrees?\b.*\b(add|pull|update|sync|vendor|refresh|import|bump|upgrade)\b'
            - or:
                - 'added-files ~= ^(?!\.mergify\.yml$|README\.md$|docs/|\.github/)'
                - 'modified-files ~= ^(?!\.mergify\.yml$|README\.md$|docs/|\.github/)'
      - -added-files ~= ^vendor/        # the repo's declared subtree prefixes
      - -modified-files ~= ^vendor/
```

A removal-only PR under a prefix matches none of the exclusions and squashes as usual. A rebased or squashed subtree PR carries the dir trailer, so `default` refuses it and `subtree` refuses it as linear: it matches no queue.

### What the org protection adds

"Subtree PRs need subtree history" in `.mergify.yml` gives a named failing check. It applies to a PR whose title pairs a subtree verb with the word subtree and that adds or modifies a file outside the Mergify config, `README.md`, `docs/` and `.github/`, and to any PR whose commits carry a `git-subtree-dir:` trailer. It fails unless the two tests above pass. Removal-only, config-only and docs-only PRs are not claims. Mergify will not merge a PR whose active protection fails.

### What stays open

Mergify does not stop a merge made outside it. A user with write access can still squash from the GitHub UI or API, because GitHub has no per-PR merge-method restriction. Requiring the `Mergify Merge Protections` check in a ruleset blocks that merge only for PRs where the protection is active.
