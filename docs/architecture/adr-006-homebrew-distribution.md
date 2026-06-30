# ADR-006: Homebrew Distribution via Custom Tap

**Status:** Accepted  
**Date:** 2026-04-11

## Context

TerraFlow is a Python CLI tool that depends on rasterio and pyproj, both of which
require system-level GDAL and PROJ shared libraries. `pip install terraflow-agro`
does not install these system libraries, leaving macOS users to resolve them manually
(typically via Homebrew or conda anyway). This creates unnecessary friction for the
most common macOS install path.

Homebrew is the de facto package manager for macOS developer tools. A Homebrew
formula can declare system-level dependencies (`gdal`, `proj`) and have them
installed automatically as part of `brew install`.

Two distribution options were considered:

| Option | Description |
|--------|-------------|
| **Homebrew Core** | Submit a formula to `homebrew/homebrew-core`; accessible via `brew install terraflow` without a tap |
| **Custom tap** | Publish a personal tap at `gmarupilla/homebrew-terraflow`; accessible via `brew tap gmarupilla/terraflow && brew install terraflow` |

## Decision

Use a **custom Homebrew tap** (`gmarupilla/homebrew-terraflow`).

## Rationale

Homebrew Core submission requires:
- ≥ 75 GitHub stars on the upstream repo (soft threshold)
- Formula review by Homebrew maintainers (timeline unpredictable)
- Ongoing compliance with Homebrew's audit rules and deprecation policy
- Commitment to keep the formula passing `brew audit --strict` at all times

A custom tap:
- Ships immediately — no review queue
- Can be automated end-to-end via CI (see `publish-homebrew.yml`)
- Is appropriate for a research-grade scientific CLI at this stage of maturity
- Can be promoted to Core later once the project has a larger install base

## Formula Design

```ruby
class Terraflow < Formula
  include Language::Python::Virtualenv
  depends_on "python@3.12"
  depends_on "proj"
  depends_on "gdal"
  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install buildpath
    bin.install_symlink Dir["#{libexec}/bin/terraflow"]
  end
end
```

- `Language::Python::Virtualenv` isolates the formula's Python environment from the
  user's system Python — no version conflicts.
- `python@3.12` is pinned to the latest stable Python LTS available in Homebrew.
  TerraFlow supports `>=3.10`; 3.12 is the current recommended target.
- `proj` and `gdal` are declared as system deps so Homebrew resolves them before
  `pip_install` attempts to build rasterio's C extensions.
- The formula source of truth lives at `packaging/homebrew/Formula/terraflow.rb`
  in the main repo and is pushed to `gmarupilla/homebrew-terraflow` on each release.

## Automation

`publish-homebrew.yml` (`.github/workflows/`) triggers on every `v*.*.*` tag push:

1. Waits for the GitHub archive tarball to become available
2. Computes its SHA-256 with `sha256sum`
3. Clones `gmarupilla/homebrew-terraflow` using `HOMEBREW_TAP_TOKEN` (a GitHub PAT)
4. Patches the formula's `url` and `sha256` fields with `sed`
5. Commits and pushes to the tap repo

This runs in parallel with `publish-pypi.yml` — neither depends on the other.

## Consequences

**Positive:**
- macOS users get a one-command install (`brew tap` once, then `brew install`)
- `brew upgrade terraflow` keeps them current without manual intervention
- GDAL and PROJ are installed and linked automatically

**Neutral:**
- Users must run `brew tap gmarupilla/terraflow` once before installing (not required
  for Core formulae, but universally understood by Homebrew users)
- Optional extras (`[viz]`, `[cmip6]`) are not available via the formula; pip must be
  used for those (documented in `docs/install/homebrew.md`)

**Future:**
- If the project reaches Homebrew Core eligibility, the formula at
  `packaging/homebrew/Formula/terraflow.rb` is ready for submission with minimal changes
