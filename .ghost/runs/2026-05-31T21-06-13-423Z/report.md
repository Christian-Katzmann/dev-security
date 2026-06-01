# Ghost Invasion Report - 2026-05-31T21-06-13-423Z

START HERE - prioritized findings from the evidence on disk.

Scale: 3 browser users in 2 waves + 2 API hits across 2 endpoints
Mode: quick --pack launch-readiness
Cost: estimated $0.0000, actual $0.0000, budget $0.0000
Target: http://127.0.0.1:8876 (manual)
Safety: no live keys - egress trap not proven (attach-only) - reset: none - stripe:blocked-stub mocked

## Verdict: 0 confirmed bugs, 1 needs your eyes.

## MEDIUM - F-001 - locator.waitFor: Error: strict mode violation: getByText('Overview') resolved to 3 elem...
Violates contract: ux.no-dead-end-after-error
Confidence: 0.60 (needs human review) - reproduced across 1 persona(s), 1 seed(s) - 1/1 attempts - pristine path FAILED

What a real user did: Used / under the recorded persona conditions and waited for the UI to recover.
What should happen: The journey invariant remains true.
What actually happens: locator.waitFor: Error: strict mode violation: getByText('Overview') resolved to 3 elements:
    1) <span>Overview</span> aka getByRole('button', { name: 'Overview' })
    2) <strong>Overview</strong> aka getByRole('strong').filter({ hasText: 'Overview' })
    3) <h3>Repository health overview</h3> aka getByRole('heading', { name: 'Repository health overview' })

Call log:
[2m  - waiting for getByText('Overview') to be visible[22m


Proof:
  - Replay: npx playwright show-trace .ghost/runs/2026-05-31T21-06-13-423Z/evidence/local-dashboard-observer.dashboard-overview-renders.01337.trace/trace.zip
  - evidence/local-dashboard-observer.dashboard-overview-renders.01337.trace/fail.png
  - evidence/local-dashboard-observer.dashboard-overview-renders.01337.trace/network.har
  - evidence/local-dashboard-observer.dashboard-overview-renders.01337.trace/trace.zip
  - evidence/local-dashboard-observer.dashboard-overview-renders.01337.trace/video.webm
  - evidence/local-dashboard-observer.dashboard-overview-renders.01337/fail-cheap.png
  - Steps to reproduce: reproduction-steps/F-001.md

Suggested fix:
  - Inspect the failing journey evidence and make the invariant deterministic before promoting this finding.
  - Regression test written for you: generated-tests/F-001.spec.ts

Folded away: 0 near-identical failure(s) collapsed into the findings above. 1 flaky or non-confirmed blip(s) are counted, not inflated.
Full machine data: report.json

