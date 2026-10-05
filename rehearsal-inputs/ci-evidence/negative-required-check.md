# SIMULATED missing required check

This isolated draft PR is a negative probe for Issue #12. It must remain unmerged and is not an application feature, integration candidate, outage report or merge waiver.

The branch adds a `pull_request.paths` filter containing only `invoice_totals/**` and `tests/**`. This PR changes only that workflow and this document, so neither changed path matches the filter. The `push` event remains restricted to `main`; all jobs and steps are preserved verbatim. The expected observation is that GitHub does not start this workflow for the PR and the protected branch's required GitHub Actions `test` context is missing for its exact head. The actual API observations determine the outcome; a skipped or successful context is a failed negative case, never evidence of a missing check.

This is a deliberately fixable repository/event mismatch. Changing the filter or the PR's paths would restore eligibility. It is expressly nonqualifying outage evidence: no provider outage, authentication failure, runner failure, quota condition, or infrastructure startup failure is being exercised. Local tests cannot satisfy the required server context, and an intended absent check does not waive any protection or ordinary integration gate.

Root alone observes the installed ordinary guard through its read-only refusal probe and judges the server evidence. This worker must not execute the guard, attempt a merge, create checks or statuses, rerun unrelated workflows, modify protection, publish a release, or admit a product bundle for this fixture PR.
