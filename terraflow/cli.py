import argparse
import sys
from pathlib import Path

from .pipeline import run_pipeline
from .utils import logger


def main() -> None:
    """Main entry point for the TerraFlow CLI."""
    parser = argparse.ArgumentParser(
        description="TerraFlow: run geospatial agricultural modeling pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  terraflow -c config.yml

Config file should be a YAML with keys: raster_path, climate_csv, roi, model_params, output_dir
        """,
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        type=Path,
        help="Path to YAML config file",
    )
    
    try:
        args = parser.parse_args()
        
        if not args.config.exists():
            parser.error(f"Config file not found: {args.config}")
            sys.exit(1)
        
        logger.info(f"TerraFlow starting with config: {args.config}")
        run_pipeline(args.config)
        logger.info("TerraFlow completed successfully")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"ERROR: Pipeline failed - {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
