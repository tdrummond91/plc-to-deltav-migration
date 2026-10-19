# Consolidated Phase 1 history

Created 2026-10-19 at Tyler's request to condense the iterative commit history.
The 122 feature-branch commits were grouped into eight meaningful milestones
above the original main baseline `b667295f49dfe28916d61efccf9c099e6d40b8c6`.
The final review-guide milestone also includes the accepted C16 test return
and history-cleanup documentation. On 2026-10-21, the workflow fix and its two
duplicate report-only commits were combined into `2553caed1927`.
Main contains 15 commits in total.

## Milestone map

| Order | Scope | Original commits | Original range | Consolidated commit |
|---|---|---:|---|---|
| 1 | map references, routine calls and SFC structure | 29 | `46467af..9cd65a4` | `044b546ee425` |
| 2 | add offline exploration of source and control evidence | 20 | `9cd65a4..f93f744` | `120ffb5b53e1` |
| 3 | explain rung conditions and instruction context | 21 | `f93f744..4018156` | `2975bb1e1d20` |
| 4 | connect control paths and execution context | 18 | `4018156..2eb51d2` | `0f0ac8075973` |
| 5 | group signal, alarm and dependency evidence | 17 | `2eb51d2..cdad803` | `caacdf4999fd` |
| 6 | resolve residual context and prepare Phase 1 review | 13 | `cdad803..47f51dd` | `c1df6b906af8` |
| 7 | organize guides and centralize report contracts | 3 | `47f51dd..1efa063` | `fe36f89088b3` |
| 8 | add embedded guidance, contextual feedback and accepted C16 validation | 1 plus return/cleanup follow-ups | `1efa063..07a935c`, C16 `23d073d` | final review-guide milestone |

Historical SHA values in reports and notes remain unchanged as provenance
identifiers. They do not guarantee that the original commit will remain
available for checkout after squash consolidation and ordinary Git cleanup.
The parser, report validation and frozen-sample replay do not depend on archive
tags or on resolving those historical commits.

## Preservation checks

The first seven milestones retain the original checkpoint's tracked blobs and
file modes, plus the pre-existing main feedback report
`public/inspection/work-check-20261014T074558Z-c76f530e.json` from `b667295`.
The final milestone retains the review-guide implementation, all documentation,
that main report and the accepted C16 return. The 2026-10-19 cleanup changed
four active documentation files. The 2026-10-21 amendment changes only this
history map; all other tracked blobs and file modes match the prior main tip.
No parser code, tests, assets, scripts, fixtures, frozen documentation snapshots
or saved report bytes change.

The workflow fix includes both original work-machine reports from `46467af`
and `b667295`. Each records 152 application cases with one skip, 139 helper
tests and no failures or errors. Analysis and test results match exactly;
only run identifiers and recorded source revisions differ. The combined
workflow commit retains the complete `b667295` tree, while the first seven
subsequent milestones retain their original trees and commit messages.

All 64 retained reports previously passed closed validation, versioned byte
caps and exact serialization replay. Frozen-history acceptance is unchanged.
The C16 return tested clean checkpoint `07a935c`: 2,122 application cases with
two expected skips, 139 helpers and a successful private report save. Its 29
analysis summaries match C15 with only `tool_revision` excluded; the complete
frozen sample and diagnostic envelopes also match. See the
[review-guide implementation](REVIEW_GUIDE_IMPLEMENTATION.md) for validation.

## Branch and history policy

Build, test and iterate on a focused `-pc` branch. Before merging to `main`,
group those iterations into meaningful feature or fix commits, with their
validation results and explanatory documentation. Routine run receipts and
status notes belong with the change they validate. Preserve the documentation
and report files; retaining every temporary development commit is unnecessary.

The completed branches `feat/bounded-operand-example-pc` and
`review/phase1-consolidated-pc` are retired. The temporary tags
`archive/phase1-before-squash-20261014` and `archive/phase1-iterations-20261019`
are also retired. They kept the original iteration histories visible to
`git log --all` without being required by the tooling. The separately tracked
documentation archive under `public/docs/history/` remains intact; statements
in those frozen snapshots describe the state when they were written.

## Work-PC synchronization

The 2026-10-19 cleanup folded the final review-guide follow-ups together. The
2026-10-21 amendment also folds two older report-only commits into their
workflow fix and replays the eight later milestones. Checkouts at `949a43d`
or the earlier `1947c32` need a one-time branch update; a normal fast-forward
pull cannot apply this rewrite.

From the repository root, first run `git status --short`. If it shows any local
changes, preserve and inspect them before continuing. With a clean checkout:

```bash
git fetch --prune origin
{ git merge-base --is-ancestor main 949a43d 2>/dev/null ||
  git merge-base --is-ancestor main 1947c32; } &&
  git switch -C main origin/main
```

The ancestor check prevents replacing a main branch containing newer local
commits. If it fails, stop and inspect those commits rather than forcing the
update. This operation does not delete ignored private engineering files.
After synchronization, delete the two retired local archive tags if present:

```bash
git tag -d archive/phase1-before-squash-20261014 archive/phase1-iterations-20261019
```

Old local branches can also keep the iteration history visible. Delete only
branches whose work is already included in main or the documented checkpoints;
do not bulk-delete branches with unreviewed local work. Normal future updates
return to `git switch main` and `git pull --ff-only`.

Open the existing private `review.html` from completed check
`20261019T201714Z-38434b5f`, using its printed private-report path or newest
completed workspace folder. No parser rerun is needed. The
[tracker](../planning/PRE_TEAM_REVIEW_TRACKER.md) records sixteen completed
cycles and zero further unchanged-source runs before engineering review.
