# Committed evaluation results

- `report.json` — DeepEval's native JSON report (kept as-is).
- `manifest.json` — integrity/freshness sidecar recording content hashes of the
  skills, task cases, and fixture outputs the report was produced from.

CI recomputes the hashes and compares them to `manifest.json`; a mismatch means
the results are stale or tampered and the PR check fails. This directory is
intentionally tracked in git.
