# Tasks: Add a frontend agent-skills store with DeepEval evals and a CI gate

Each task is a working, demoable increment that builds on the previous one.
Wire everything together at the end; no orphaned code.

## 1. Bootstrap repo skeleton + Python eval tooling

- [ ] 1.1 Create the directory structure (`skills/`, `evals/{content,application,cases,fixtures,results,lib}`, `scripts/`, `.github/workflows/`).
- [ ] 1.2 Add Python project config for the `evals` package (pyproject or requirements) pinning **DeepEval** and **pytest** to exact versions.
- [ ] 1.3 Add a minimal `README.md` stub.
- [ ] 1.4 Add a `.gitignore` that ignores venv/cache but **explicitly tracks** `evals/fixtures/` and `evals/results/`.
- **Test:** `pip install` succeeds and `pytest --collect-only` runs clean with zero tests.
- **Demo:** in a clean environment, install then run `deepeval --version` and `pytest --collect-only` successfully.

## 2. Author the seed exemplar skill `govuk-accessible-component`

- [ ] 2.1 Write a spec-conformant `SKILL.md` (valid frontmatter + instructions to produce an accessible GOV.UK Design System component).
- [ ] 2.2 Add a `references/` file; optional `assets/`.
- [ ] 2.3 Keep `SKILL.md` under ~500 lines; `name` matches directory; lowercase-hyphenated; include when-to-use keywords and accessibility outcomes.
- **Test:** `skills-ref validate ./skills/govuk-accessible-component` (or a local frontmatter check) passes.
- **Demo:** validator reports a clean pass.

## 3. Content-eval suite (concern A) with shared skill-loading + hashing lib

- [ ] 3.1 Implement `evals/lib` helpers to discover skills and compute content hashes.
- [ ] 3.2 Implement `evals/content/test_skill_content.py` with deterministic spec-conformance checks (required fields, naming, size limits) as **hard assertions**.
- [ ] 3.3 Add at least one DeepEval **G-Eval** metric for clarity/completeness, run locally with the developer's own model.
- **Test:** content suite passes for the seed skill; prove failures are caught by temporarily adding a malformed skill, then remove it.
- **Demo:** `deepeval test run evals/content` passes locally.

## 4. Eval case format + local generation helper `scripts/generate.py`

- [ ] 4.1 Define the task-case YAML schema (`evals/cases/<skill>/<case-id>.yaml`: task prompt, skill reference, expected criteria).
- [ ] 4.2 Implement `scripts/generate.py` to ingest locally-generated output, write it to `evals/fixtures/<skill>/<case-id>/`, and record content hashes (skill + case + output) into `evals/results/manifest.json`. It does **not** call an LLM itself.
- **Test:** unit tests for the hashing/manifest write; running the helper produces a fixture + a manifest entry with stable hashes.
- **Demo:** run `scripts/generate.py` on a sample output and show the new fixture file and manifest entry.

## 5. Application-eval suite (concern B) writing the native report

- [ ] 5.1 Implement `evals/application/test_skill_application.py` to load each case + its committed fixture output and grade it with DeepEval metrics (e.g., G-Eval correctness/relevance vs expected criteria) using the local LLM.
- [ ] 5.2 Configure the run to emit DeepEval's **native JSON report** to `evals/results/report.json`, with content-concern vs application-concern outcomes clearly separated (per-case pass/fail + concern label).
- [ ] 5.3 Reuse the Task 3/4 libs.
- **Test:** application suite passes for the seed fixture; confirm `report.json` is written and parseable.
- **Demo:** `deepeval test run evals` produces `report.json` with both sections populated.

## 6. CI-side verifier `scripts/verify_results.py` — freshness + pass/fail adjudication

- [ ] 6.1 Implement `scripts/verify_results.py` (no LLM/agent): validate `report.json` schema; recompute hashes of current committed skills/cases/fixtures and compare to `manifest.json`; exit non-zero if results are missing, stale, tampered, or any recorded case failed.
- [ ] 6.2 Produce clear, actionable failure messages (e.g., "results stale for skill X — regenerate and re-run evals locally").
- **Test:** unit tests for pass, stale-hash mismatch, missing report, and recorded-failure cases.
- **Demo:** run the verifier against good results (exit 0), mutate a skill file, re-run to show a staleness failure (non-zero).

## 7. GitHub Action workflow wiring the gate

- [ ] 7.1 Add `.github/workflows/evals.yml` running on PRs: set up Python, install **only** what `verify_results.py` needs (no DeepEval/LLM), run the verifier, pass/fail the PR.
- [ ] 7.2 No secrets/API keys; fast and deterministic; surface the verifier message in the job summary.
- **Test:** validate workflow syntax; confirm it fails on stale/failing results and passes on fresh/passing results.
- **Demo:** PR check passes on valid committed results and fails on a stale/tampered fixture.

## 8. README + end-to-end wiring/documentation

- [ ] 8.1 Write the `README.md`: repo purpose, the two eval concerns, the full local workflow (author skill → define case → generate output locally → run evals → commit report+manifest+fixtures → PR), and how the CI gate works.
- [ ] 8.2 Add a top-level `make`/script entrypoint tying generate → eval → verify together.
- [ ] 8.3 Document exact commands, the freshness model, and how to add a new skill; ensure no orphaned scripts (everything reachable from documented commands).
- **Test:** follow the README from scratch on the seed skill to produce committed results and a green local verifier run.
- **Demo:** a new contributor goes from clone to a passing local verify by following the README; the CI gate mirrors the outcome.
