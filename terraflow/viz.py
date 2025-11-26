from pathlib import Path

import pandas as pd
import plotly.express as px


def plot_suitability_scatter(
    df: pd.DataFrame,
    lat_col: str = "lat",
    lon_col: str = "lon",
    score_col: str = "score",
    output_html: str | Path | None = None,
):
    """
    Create an interactive scatter map of suitability scores using Plotly.

    This assumes the DataFrame contains latitude, longitude, and a score in [0,1].
    """
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
        fig.write_html(output_html)

    return fig
