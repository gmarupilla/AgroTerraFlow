## Summary

<!--
Briefly describe what changed and why. Link the issue(s) this closes.
For non-trivial changes, lead with the *why* — reviewers can read the diff
for the *what*.
-->

Closes #

## Type of change

<!-- Tick all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would change existing behaviour)
- [ ] Docs / paper / CI / packaging only (no runtime behaviour change)
- [ ] Reproducibility-affecting change (touches `run_identity`, fingerprints,
      atomic writes, or anything that could change run output for the same
      input)

## PR checklist

<!--
Per CLAUDE.md, every PR should keep README/docs/notebook/mkdocs/CHANGELOG in
sync. Tick what applies; strike (~~text~~) what does not.
-->

- [ ] `make lint` passes (ruff + black)
- [ ] `make typecheck` passes (mypy)
- [ ] `make test-cov` passes with coverage ≥ 85 % (`fail_under = 85` in
      `pyproject.toml`)
- [ ] `make smoke-test` passes for end-to-end-touching changes
- [ ] `CHANGELOG.md` `[Unreleased]` section updated
- [ ] `README.md` updated if user-facing behaviour or install changes
- [ ] `docs/` updated (guide / ADR / API page) for user-facing changes
- [ ] Jupyter notebook in `docs/notebooks/` added or updated, and
      `mkdocs.yml` nav reflects it
- [ ] No `# nosec` / `# noqa` added without a justification comment
- [ ] No backwards-compat shims added for unreleased code paths

## Reproducibility impact

<!--
Required only if you ticked "Reproducibility-affecting change" above.
Describe how the run_fingerprint or the GeoAI fingerprint is impacted, and
whether existing cached runs need invalidation.
-->

## Verification

<!--
How did you test this? Concrete commands beat narrative.
Example: pasted pytest output, screenshots of mkdocs renders, a
before/after of a manifest.json, the `terraflow ...` command you ran.
-->
