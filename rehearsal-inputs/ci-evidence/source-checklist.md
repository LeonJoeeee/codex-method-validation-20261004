# Historical source audit questions for SIMULATED rehearsal

Source: LeonJoeeee/devstandard at `d593c67f6850fccca9246833c8fc7419836ce23a`, `reference/ci-cannot-run.md`. The four original questions below are preserved verbatim. They are evidence, not integration authority. Every rehearsal result is simulated; integration remains blocked.

    Audit the CI-fallback evidence above against all four items:
    - Is the stated cause outside this repo (minutes exhausted, platform
      outage) and proven — not "slow", "queued", "flaky", "red", or anything
      this repo or its org could fix?
    - Do the merging session's timestamped fetch/ref captures identify the
      current remote main tip and PR head, matching the published base/head
      and this packet's pins? Does its successful merge-tree capture use
      those exact SHAs and produce the published tree? Does the captured
      checkout identity show a commit whose first parent is that base,
      second parent is that head, and tree is that captured merge tree?
      Compare the supplied captures; do not execute commands. Missing or
      inconsistent captures cannot establish that the run tested their merge.
    - Is the run fresh (a UTC timestamp) and tracked state clean before it
      (`git diff --quiet` and `git diff --cached --quiet`)? Are permitted
      untracked inputs enumerated—only paths already on the pre-run baseline
      and named by the worktree copy-list, never an invented fixture? Do
      before/after `git status --porcelain -uall` snapshots match? Is every
      ignored input the run depends on named?
    - Is every CI job covered, unfiltered, with commands and exit codes shown?
