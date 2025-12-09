from pathlib import Path

import pandas as pd
from plotly.graph_objs import Figure

from terraflow.viz import plot_suitability_scatter


def test_plot_suitability_scatter_basic():
    """
    Smoke test: ensure that plot_suitability_scatter returns a Plotly Figure
    and that the figure contains at least one trace.

    This uses a tiny in-memory DataFrame and does not write to disk.
    """
    df = pd.DataFrame(
        {
            "lat": [39.0, 39.5, 40.0],
            "lon": [-94.5, -95.0, -95.5],
            "score": [0.2, 0.5, 0.9],
        }
    )

    fig = plot_suitability_scatter(df)

    assert isinstance(fig, Figure)
    assert len(fig.data) > 0
    assert fig.layout.mapbox is not None
    # we set this in the implementation
    assert fig.layout.mapbox.style == "open-street-map"


def test_plot_suitability_scatter_output_html(tmp_path: Path):
    """
    Ensure that when output_html is provided, an HTML file is written.
    """
    df = pd.DataFrame(
        {
            "lat": [39.1, 39.2],
            "lon": [-94.6, -94.7],
            "score": [0.3, 0.7],
        }
    )

    output_path = tmp_path / "viz.html"
    fig = plot_suitability_scatter(df, output_html=output_path)

    assert isinstance(fig, Figure)
    assert output_path.exists()
    assert output_path.is_file()
