# Installing TerraFlow via Homebrew

Homebrew is the recommended installation method for macOS users. It automatically
handles the GDAL and PROJ system-library dependencies that rasterio and pyproj require.

## Prerequisites

- macOS 12 (Monterey) or later
- [Homebrew](https://brew.sh) installed

## Install

```bash
brew tap gmarupilla/terraflow
brew install terraflow
```

The install step builds a Python 3.12 virtualenv in the Homebrew prefix and symlinks
`terraflow` into your PATH. Expect a few minutes the first time — GDAL and PROJ may
compile from source.

## Verify

```bash
terraflow --help
```

You should see the usage message listing `run`, `sensitivity`, `validate`, and `export`.

## Update

```bash
brew update
brew upgrade terraflow
```

`brew update` fetches the latest formula from the tap; `brew upgrade` installs it.
The tap formula is updated automatically on every tagged release via
[`publish-homebrew.yml`](https://github.com/gmarupilla/AgroTerraFlow/blob/main/.github/workflows/publish-homebrew.yml).

## Uninstall

```bash
brew uninstall terraflow
brew untap gmarupilla/terraflow   # optional: remove the tap entirely
```

## Optional Extras

The `[h3]` and `[viz]` extras are not available via the Homebrew formula because
Homebrew virtualenvs are isolated. To use H3 export or Plotly visualizations,
install via pip instead:

```bash
pip install "terraflow-agro[h3]"        # H3 hexagonal export
pip install "terraflow-agro[viz]"       # Plotly visualization support
pip install "terraflow-agro[h3,viz]"    # both
```

## Troubleshooting

### GDAL environment variable conflicts

If you see `CPLE_AppDefined` errors or rasterio emits `NotGeoreferencedWarning`,
a stale environment variable may be overriding the Homebrew-managed GDAL. Unset it:

```bash
unset GDAL_DATA GDAL_DRIVER_PATH PROJ_LIB
```

If the issue persists, reinstall the formula:

```bash
brew reinstall terraflow
```

### PROJ database not found

Symptom: `pyproj.exceptions.CRSError: PROJ: proj_create_from_database`

Fix:

```bash
brew reinstall proj
```

If you have a system PROJ (conda, MacPorts) alongside the Homebrew one, check which
takes precedence:

```bash
which proj   # should resolve to /opt/homebrew/bin/proj (Apple Silicon)
             #                  or /usr/local/bin/proj (Intel)
```

### `brew install` fails during GDAL build

On a fresh machine, the build can fail if Xcode Command Line Tools are incomplete:

```bash
xcode-select --install
brew install gdal
brew install terraflow
```

### Formula not found after `brew tap`

```bash
brew tap --repair gmarupilla/terraflow
brew install terraflow
```

### Install the development HEAD

```bash
brew install --HEAD terraflow
```

Not recommended for production use — this clones the `main` branch directly.
