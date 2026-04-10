# Phase 4: H3 Export — Discussion Log

**Session:** 2026-04-02
**Format:** Interactive (discuss mode)

---

## Areas Discussed

All four gray areas selected: Resolution config vs CLI flag, Aggregation method, Output columns, Artifact location.

---

## Resolution Parameter

**Q: Where does the H3 resolution parameter live?**
Options: export: section in config.yml / --resolution CLI flag only / Both: config default + CLI override
**Selected:** Both: config default + CLI override

**Q: When --resolution overrides the config default, should the fingerprint use the CLI-provided value?**
Options: Yes — CLI value goes into fingerprint / No — fingerprint uses config value only
**Selected:** Yes — CLI value goes into fingerprint (recommended)

---

## Aggregation Method

**Q: When multiple pipeline cells fall in the same H3 hex, how should numeric columns be aggregated?**
Options: Mean for all numeric columns / Mean for score only / User decides at call time (aggfunc param)
**Selected:** Mean for all numeric columns (recommended)

**Q: How should the label column (categorical) be handled during aggregation?**
Options: Mode (most frequent label) / Drop it / Derive from aggregated score
**Selected:** Mode (most frequent label) (recommended)

---

## Output Columns

**Q: What columns should the to_h3() DataFrame expose?**
Options: All features (score + v_index + mean_temp + total_rain + label) / Score + label only / Score only
**Selected:** All features: score + v_index + mean_temp + total_rain + label (recommended)

---

## Artifact Location

**Q: Where does terraflow export write the H3 output file?**
Options: Inside runs/<fingerprint>/ / Standalone in output_dir root
**Selected:** Inside runs/<fingerprint>/ alongside features.parquet (recommended)

---

*Discussion complete — context written to 04-CONTEXT.md*
