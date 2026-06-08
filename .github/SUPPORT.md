# Getting Support

Thanks for using TerraFlow. Below are the channels for help, sorted by what
you're trying to do.

## Read the docs first

- **Documentation site:** [terraflow.marupilla.dev](https://terraflow.marupilla.dev) —
  quickstart, field guide, configuration schema, CLI reference, GeoAI guide,
  reproducibility page, architecture decision records.
- **Notebooks:** end-to-end examples under
  [`docs/notebooks/`](../docs/notebooks/) (climate pipeline, kriging
  uncertainty, sensitivity, validation, H3 export, GeoAI engine).
- **CHANGELOG:** [`CHANGELOG.md`](../CHANGELOG.md) — what shipped in each
  release, including breaking changes.

## Ask a question / start a discussion

- **GitHub Discussions** (if enabled on the repo) is the preferred place for
  open-ended questions, design conversations, and "how do I do X with
  TerraFlow" threads.
- If Discussions is not enabled and your question is open-ended, open a
  GitHub issue using the **feature request** template — questions are welcome
  there too.

## Report a bug or regression

- Use the **bug report** issue template:
  [open a new bug](https://github.com/gmarupilla/AgroTerraFlow/issues/new?template=bug_report.yml).
- Please include the YAML config and the `run_fingerprint` from
  `<output_dir>/runs/<fingerprint>/manifest.json` — reproducibility is the
  point of TerraFlow, and that pair lets us recreate the failing run exactly.

## Reproducibility-specific questions

- Read [`docs/reproducibility.md`](../docs/reproducibility.md) first — it
  documents what the fingerprint covers, the known sources of
  non-determinism (pykrige variogram fit across scipy versions, qhull
  triangulation tie-breaking, BLAS-dependent summation order, GeoAI device
  + torch-minor sensitivity), and a reviewer-oriented citation checklist.
- If your output is still drifting after following that doc, open a bug
  report and we will treat it as a reproducibility regression (highest
  priority).

## Report a security vulnerability

- **Do not** open a public issue. Use GitHub Security Advisories:
  [report a vulnerability](https://github.com/gmarupilla/AgroTerraFlow/security/advisories/new).
- See [`SECURITY.md`](../SECURITY.md) for the disclosure policy and supported
  versions.

## Contribute code

- See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the dev setup
  (`make venv && make dev`), the testing workflow (`make lint typecheck
  test-cov`), the PR checklist (README + docs + notebook + mkdocs nav +
  CHANGELOG entry per `CLAUDE.md`), and the commit-message conventions.
- The `.github/pull_request_template.md` will pre-populate the checklist when
  you open a PR.

## Commercial support

TerraFlow is maintained on a best-effort volunteer basis. Commercial support,
integration consulting, and priority feature work are available — contact
the corresponding author listed in [`CITATION.cff`](../CITATION.cff).
