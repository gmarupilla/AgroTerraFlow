import argparse
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TerraFlow: run geospatial agricultural modeling pipeline"
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to YAML config file",
    )
    args = parser.parse_args()

    run_pipeline(Path(args.config))


if __name__ == "__main__":
    main()
