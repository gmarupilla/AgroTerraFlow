"""
Generate meaningful example plots for the TerraFlow paper.

This script produces a suitability heatmap instead of a histogram.
"""

from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs" / "demo_run"
PAPER_DIR = ROOT / "paper"


def main() -> None:
    csv_path = OUTPUTS / "results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Expected {csv_path} to exist. Run the demo pipeline first."
        )

    df = pd.read_csv(csv_path)

    PAPER_DIR.mkdir(exist_ok=True)

    # ----------------------------------------------------------------------
    # Attempt to build a heatmap if x, y, score columns exist.
    # If no x,y available, generate a scatter instead.
    # ----------------------------------------------------------------------

    if {"x", "y", "score"}.issubset(df.columns):
        # Pivot into a 2D grid for heatmap
        heatmap = df.pivot_table(values="score", index="y", columns="x", aggfunc="mean")

        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(heatmap.values, cmap="viridis", aspect="auto",
                       origin="lower")

        ax.set_title("Spatial Suitability Heatmap")
        ax.set_xlabel("X coordinate index")
        ax.set_ylabel("Y coordinate index")

        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("Suitability Score")

        fig.tight_layout()
        fig.savefig(PAPER_DIR / "figure3.png", dpi=300)

    else:
        # Fallback scatter plot
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(df.index, df["score"], s=8, alpha=0.6)

        ax.set_title("Suitability Score Distribution")
        ax.set_xlabel("Sample Index")
        ax.set_ylabel("Suitability Score")

        fig.tight_layout()
        fig.savefig(PAPER_DIR / "figure3.png", dpi=300)


if __name__ == "__main__":
    main()
