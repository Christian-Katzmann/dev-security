# Behavioral Drift Evidence Threshold

Behavioral drift is an investigation signal, not a compromise verdict.

Run it only after SBOM history shows a dependency version change. The advanced check compares old and new local package artifacts with malcontent when both artifacts are available and within bounds.

Threshold for creating a finding:

- The package must have existed in the previous SBOM and the latest SBOM.
- The saved version must have changed.
- Both old and new artifact files or directories must exist locally.
- Each artifact must be 50 MB or smaller.
- The scan must stay within 5 changed package versions and 20,000 artifact files.
- malcontent must report a higher-risk behavior in the new artifact.

Missing old artifacts, missing new artifacts, oversized artifacts, missing versions, scanner timeouts, and malcontent errors are recorded as `not_checked`. They are not evidence of compromise and do not fail the scan.

What this can prove: a package artifact appears to have gained behavior worth reviewing.

What this cannot prove: that the package is malicious, that compromise happened, or that the behavior is reachable in Christian's project.
