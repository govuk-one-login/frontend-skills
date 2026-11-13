# frontend-skills

A lightweight, version-controlled store of **agent skills** for frontend
engineering and testing, with a GOV.UK Design System (GDS) flavour. Skills are
evaluated with [DeepEval](https://deepeval.com) along two separate concerns, and
pull requests are gated by a **key-free** GitHub Action that adjudicates
committed results.

## Why this design

CI has **no agent/LLM access and no API keys**. So the expensive,
non-deterministic work (generating output and running LLM-judge metrics) happens
**locally** with [Ollama](https://ollama.com) using two pinned models. The
results, an integrity manifest, and a tamper-evident **signature** are
**committed**, and CI only performs a fast, deterministic **adjudication**: it
recomputes content hashes and the signature to prove freshness and integrity,
enforces the pinned models, re-checks every graded score against its threshold,
and checks that every recorded case passed. This keeps CI fast, deterministic,
and fork-friendly.

## Pinned models

Local evaluation uses two pinned [Ollama](https://ollama.com) models so results
are comparable across developers (defined in `evals/lib/models.py`):

- **Generation** — `qwen2.5:7b` produces fixture output for an application task
  case (`scripts/generate.py --generate`).
- **Judge** — `qwen2.5:14b` is the DeepEval G-Eval judge used by both suites.

CI never runs a model, but it does assert the committed, signed results were
produced with these exact pinned models.

## The two eval concerns

Evaluation is split into two explicitly separate concerns:

- **Content quality (concern A)** — are the skill documents themselves valid,
  clear, complete, and free of contradictions? Lives in `evals/content/`.
  - Deterministic spec-conformance checks (hard assertions): required
    frontmatter, `name`/`description` constraints, name-matches-directory, size
    limits. These always run, with or without a model.
  - An LLM-judge (G-Eval) clarity/completeness metric, run locally with the
    pinned judge model (`qwen2.5:14b`). Skipped automatically when no model is
    available.
- **Application quality (concern B)** — when an agent applies a skill to a task,
  is the produced output good? Lives in `evals/application/`.
  - A deterministic gate requiring a non-empty committed fixture per case.
  - An LLM-judge (G-Eval) metric grading the committed fixture against the
    case's expected criteria, using the pinned judge model (`qwen2.5:14b`).
    Skipped automatically when no model is available.

Both concerns are recorded, kept separate, in `evals/results/report.json`.

## Repository layout

```
frontend-skills/
├── skills/<skill-name>/           # agent skills (Agent Skills spec)
│   └── govuk-accessible-component/
│       ├── SKILL.md
│       └── references/
├── evals/
│   ├── content/                   # concern A — skill-document checks
│   ├── application/               # concern B — grades committed fixtures
│   ├── cases/<skill>/<case>.yaml  # task definitions
│   ├── fixtures/<skill>/<case>/   # committed, locally-generated outputs
│   ├── results/
│   │   ├── report.json            # per-case pass/fail + scores, split by concern
│   │   ├── manifest.json          # integrity/freshness hashes + generation model
│   │   └── signature.json         # tamper-evident HMAC over report + manifest + models
│   ├── lib/                       # shared helpers (skills, cases, hashing, manifest, models, signing, reporting)
│   └── conftest.py                # writes report.json at the end of a run
├── scripts/
│   ├── generate.py                # generate (Ollama) or record output into fixtures + manifest
│   ├── sign_results.py            # sign committed results (tamper-evidence)
│   └── verify_results.py          # CI-side adjudicator (no LLM, no keys)
├── .github/workflows/evals.yml    # the CI gate
├── Makefile                       # install / generate / eval / verify entrypoints
├── requirements-ci.txt            # CI-only deps (no DeepEval)
└── evals/requirements.txt         # full local deps (DeepEval + pytest)
```

## Prerequisites

- Python 3.10+ (the local dev stack was verified on 3.14; CI uses 3.12).
- For the LLM-judge metrics locally: [Ollama](https://ollama.com) installed. You
  do not need to start it or pull the models by hand — `make ollama-up` (also
  run by `make refresh`) starts the server if needed and pulls the two pinned
  models:

  ```bash
  make ollama-up      # start the Ollama server + pull qwen2.5:7b and qwen2.5:14b
  ```

  Under the hood the server is a background daemon on `http://localhost:11434`
  (override with `LOCAL_MODEL_BASE_URL`); models are downloaded once and then
  loaded on demand. If you prefer to manage it yourself: install from
  [ollama.com](https://ollama.com), ensure the server is running (the desktop
  app, `ollama serve`, or `brew services start ollama`), and
  `ollama pull qwen2.5:7b && ollama pull qwen2.5:14b`.

  Without a model the deterministic gates still run and the G-Eval metrics are
  skipped. Another DeepEval-supported provider (e.g. `OPENAI_API_KEY`) also
  satisfies the availability check, but the pinned-model policy in CI expects
  the Ollama models above.

## Quick start

```bash
make refresh        # one command: install, regenerate fixtures, eval, sign, verify
```

`make refresh` is the whole local loop in one go. It installs the stack, checks
Ollama is ready, regenerates every fixture with the pinned generation model,
runs both suites with the pinned judge, signs the results, and adjudicates them
the way CI will.

Prefer the individual steps? They compose the same pipeline:

```bash
make install        # create .venv and install the full local eval stack
make eval           # run both suites; (re)writes evals/results/report.json
make sign           # sign the results into evals/results/signature.json
make verify         # adjudicate the committed results the same way CI does
```

`make all` runs `eval`, `sign`, then `verify` (without reinstalling or
regenerating). `make help` lists every target.

> **Do I need both models loaded at once?** No. Generation (`qwen2.5:7b`) and
> judging (`qwen2.5:14b`) run in separate phases, so Ollama only ever needs one
> loaded at a time and will swap as needed. If your machine has the memory
> (~14 GB free for both), Ollama can keep both resident — tune this with the
> server's `OLLAMA_MAX_LOADED_MODELS` — but it is not required.

## The full local workflow

1. **Author or edit a skill** under `skills/<skill-name>/` (see
   [Adding a new skill](#adding-a-new-skill)).
2. **Define a task case** at `evals/cases/<skill>/<case-id>.yaml`:

   ```yaml
   id: text-input-basic
   skill: govuk-accessible-component
   task: >-
     Build an accessible GOV.UK text input for a user's full name, with a
     label and a hint.
   expected_criteria:
     - Uses a <label> associated with the input via for/id
     - Associates hint text with the input via aria-describedby
     - Uses GOV.UK Design System classes
   ```

3. **Produce the output locally.** Either generate it with the pinned Ollama
   model, or record output you produced with your own agent:

   ```bash
   # Generate with the pinned Ollama model (qwen2.5:7b):
   make generate CASE=evals/cases/govuk-accessible-component/text-input-basic.yaml GENERATE=1

   # Or record output you produced yourself:
   make generate CASE=evals/cases/govuk-accessible-component/text-input-basic.yaml \
                 OUTPUT=path/to/your_generated_output.md

   # Or pipe from your own agent:
   your-agent ... | .venv/bin/python scripts/generate.py \
       --case evals/cases/govuk-accessible-component/text-input-basic.yaml --stdin
   ```

   This copies the output to `evals/fixtures/<skill>/<case-id>/` and records the
   skill, case, and fixture content hashes — plus the generation model used —
   into `evals/results/manifest.json`.

4. **Run the eval suites locally** (with Ollama running so the G-Eval metrics
   actually score):

   ```bash
   make eval
   ```

   This writes `evals/results/report.json` with both concerns' per-case
   pass/fail and the graded score + threshold for each judged case.

5. **Sign the results** so CI can detect tampering:

   ```bash
   make sign
   ```

   This writes `evals/results/signature.json`.

6. **Commit** the skill, the case, the fixture, and the results
   (`report.json` + `manifest.json` + `signature.json`).

7. **Open a PR.** The CI gate adjudicates your committed, signed results.

`make all` runs steps 4–6's local equivalent (`eval` → `sign` → `verify`) in one
go.

## How the CI gate works

`.github/workflows/evals.yml` runs on pull requests (and pushes to `main`). It:

1. Checks out the repo and sets up Python.
2. Installs **only** `requirements-ci.txt` — **no DeepEval, no LLM client**.
3. Runs `scripts/verify_results.py`, which:
   - Validates `report.json` (schema, structure).
   - Validates `manifest.json`.
   - Validates `signature.json` and **recomputes** the HMAC over the committed
     `report.json` + `manifest.json` + pinned model names, failing on any
     mismatch (so a hand-edited report is rejected).
   - Enforces that the signed generation/judge models are the repo's pinned
     models.
   - **Recomputes** the content hashes of the current committed skills, cases,
     and fixtures and compares them to the manifest.
   - **Re-asserts** `score >= threshold` for every graded case that carries a
     score.
   - Fails if results are missing, invalid, **stale/tampered** (any hash or
     signature mismatch), below threshold, or if **any recorded case failed**.

It requires no secrets and works for fork PRs. The pass/fail message is written
to the GitHub job summary.

## The freshness / integrity model

`report.json` is the outcome; `manifest.json` binds that outcome to the exact
content it was produced from; `signature.json` seals all of it against editing.

For each skill (content concern) and each case (application concern), the
manifest stores a sha256 content hash of:

- the skill directory (`skills/<skill>/`),
- the task case (`evals/cases/<skill>/<case-id>.yaml`),
- the fixture output directory (`evals/fixtures/<skill>/<case-id>/`), and
- the generation model used to produce the fixture.

Directory hashes are order- and OS-independent (a sha256 over a sorted list of
`relative-path → file-hash` pairs). If you change a skill, case, or fixture but
do not regenerate the results, CI recomputes a different hash than the one in
the manifest and **fails the PR**.

`signature.json` is an HMAC-SHA256 over the exact committed bytes of
`report.json` and `manifest.json` plus the pinned model names. If you hand-edit
either file after signing (for example flipping a failure to a pass or raising a
score), CI recomputes a different signature and **fails the PR**.

> **Threat model.** The signature is **tamper-evidence, not anti-forgery**. The
> HMAC key lives in the repository on purpose, so CI stays key-free and fork PRs
> just work. It reliably catches accidental edits, stale commits, and casual
> gaming, and binds the report to the pinned models — but a motivated insider
> who reads the key could recompute a valid signature. Upgrading to anti-forgery
> (asymmetric signing / an allow-list of public keys) is a localised change to
> `evals/lib/signing.py` and `scripts/verify_results.py`.

To fix a staleness/signature failure: re-run `make generate` for the affected
case (to refresh the manifest hashes), `make eval` (to refresh `report.json`),
`make sign` (to refresh the signature), then commit.

## Adding a new skill

1. Create `skills/<skill-name>/SKILL.md` following the open
   [Agent Skills spec](https://agentskills.io):
   - YAML frontmatter with required `name` and `description`.
   - `name` is 1–64 chars, lowercase alphanumeric + hyphens (no leading/trailing
     or consecutive hyphens) and **must match the directory name**.
   - `description` is 1–1024 non-empty characters.
   - Keep `SKILL.md` under ~500 lines; add `references/`, `scripts/`, or
     `assets/` as needed.
2. Add at least one task case under `evals/cases/<skill-name>/`.
3. Follow the [local workflow](#the-full-local-workflow) to generate a fixture,
   run the evals, and commit the results.

The content suite discovers every skill automatically, so the new skill is
immediately subject to the deterministic spec-conformance checks.

## Commands reference

| Command | What it does |
|---|---|
| `make install` | Create `.venv`, install the full local eval stack (DeepEval + Ollama client + pytest). |
| `make install-ci` | Install only the key-free verifier deps (no DeepEval). |
| `make refresh` | **One command**: install, check Ollama, regenerate fixtures, eval, sign, verify. |
| `make check-ollama` | Verify Ollama is running and the pinned models are pulled. |
| `make ollama-up` | Start the Ollama server (if needed) and pull the pinned models. |
| `make regenerate` | Regenerate fixtures for every committed case with the pinned Ollama model. |
| `make generate CASE=… GENERATE=1` | Generate a fixture with the pinned Ollama model and record it. |
| `make generate CASE=… OUTPUT=…` | Record an output you produced yourself into fixtures + manifest. |
| `make eval` | Run both eval suites; (re)write `evals/results/report.json`. |
| `make sign` | Sign the committed results into `evals/results/signature.json`. |
| `make verify` | Adjudicate committed results exactly as CI does (key-free). |
| `make test` | Run the tooling unit tests (lib, generate, verifier, signing). |
| `make all` | `eval` → `sign` → `verify`. |

All scripts are reachable from these documented commands — there are no orphaned
entrypoints. `scripts/generate.py`, `scripts/sign_results.py`,
`scripts/verify_results.py`, and `scripts/check_ollama.py` (with `--ensure` to
start the server and pull models) can also be invoked directly with `--help`.
