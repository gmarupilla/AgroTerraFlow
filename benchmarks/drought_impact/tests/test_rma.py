from drought_impact.rma import COL_COLUMNS, DROUGHT_DESCRIPTION, load_col, parse_col_file


def test_col_schema_is_thirty_fields():
    assert len(COL_COLUMNS) == 30


def test_parse_builds_geoid_and_numeric(bench_cfg):
    path = bench_cfg.rma_data_dir / "colsom_2012.txt"
    df = parse_col_file(path)
    assert "GEOID" in df.columns
    assert df["GEOID"].str.len().eq(5).all()
    assert df["liability"].notna().all()
    # 5-digit GEOID == zero-padded state(2) + county(3).
    assert set(df["GEOID"]) <= {"17001", "17003", "19001", "19003"}


def test_load_col_filters_states_and_crop(bench_cfg):
    df = load_col(bench_cfg)
    assert (df["commodity_name"].str.upper() == "CORN").all()
    assert set(df["state_code"]) <= {"17", "19"}
    # The gate: the "Drought" description parses verbatim, no code-table lookup.
    assert DROUGHT_DESCRIPTION in set(df["cause_of_loss_description"])


def test_zero_loss_county_year_has_no_drought_row(bench_cfg):
    df = load_col(bench_cfg)
    subset = df[(df["GEOID"] == "17003") & (df["commodity_year"] == 2010)]
    assert (subset["cause_of_loss_description"] != DROUGHT_DESCRIPTION).all()
