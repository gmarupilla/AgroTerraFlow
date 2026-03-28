"""Visualization utilities for TerraFlow results."""

from pathlib import Path

import pandas as pd


def plot_suitability_scatter(
    df: pd.DataFrame,
    lat_col: str = "lat",
    lon_col: str = "lon",
    score_col: str = "score",
    output_html: str | Path | None = None,
):
    """
    Create an interactive scatter map of suitability scores using Plotly.

    Generates a Mapbox-based interactive scatter plot where each point represents
    a sampled location, colored by suitability score and sized proportionally.
    Uses OpenStreetMap tiles for context.

    Parameters
    ----------
    df:
        Results DataFrame with latitude, longitude, and score columns.
    lat_col:
        Name of the latitude column (default 'lat').
    lon_col:
        Name of the longitude column (default 'lon').
    score_col:
        Name of the suitability score column (default 'score').
    output_html:
        Optional path to save the plot as an interactive HTML file.

    Returns
    -------
    plotly.graph_objects.Figure:
        Interactive Plotly figure object.

    Raises
    ------
    ValueError:
        If required columns are missing from the DataFrame.

    Examples
    --------
    >>> df = pd.DataFrame({
    ...     'lat': [40.0, 40.01],
    ...     'lon': [-100.0, -100.01],
    ...     'score': [0.8, 0.6]
    ... })
    >>> fig = plot_suitability_scatter(df, output_html='map.html')
    """
    try:
        import plotly.express as px
    except ImportError as e:
        raise ImportError(
            "plotly is required for visualization. "
            "Install with: pip install terraflow[viz]"
        ) from e
    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"DataFrame must contain '{lat_col}' and '{lon_col}' columns.")
    if score_col not in df.columns:
        raise ValueError(f"DataFrame must contain '{score_col}' column.")

    fig = px.scatter_mapbox(
        df,
        lat=lat_col,
        lon=lon_col,
        color=score_col,
        color_continuous_scale="Viridis",
        size=score_col,
        size_max=15,
        zoom=3,
        title="Suitability Scores",
    )
    fig.update_layout(mapbox_style="open-street-map")

    if output_html is not None:
        output_html = Path(output_html)
        output_html.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(output_html)

    return fig
