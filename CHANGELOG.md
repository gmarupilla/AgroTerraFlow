# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

- Added deterministic run fingerprinting based on canonical config, ROI geometry, and input file fingerprints.
- Introduced run identity utilities and pipeline integration for early fingerprint computation.
- Added run identity tests and updated documentation for run fingerprinting.
- Added shapely dependency for ROI geometry hashing.

## [0.2.0]

- Initial public release of TerraFlow.
- Added spatial climate interpolation with fallback strategies.
- Introduced Pydantic v2 config validation and CLI workflow runner.
- Published MkDocs documentation and ADRs.
- Added comprehensive test suite and example data.
