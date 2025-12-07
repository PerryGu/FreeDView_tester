"""
Main CLI entry point for FreeDView Tester.

This module provides a unified command-line interface for running
all phases of the FreeDView testing pipeline.
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

import jsonLocalizer as json_localizer
import freeDViewRunner
import renderCompare


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_ini_path(ini_path: Optional[str] = None) -> str:
    """
    Get the path to the INI configuration file.

    Args:
        ini_path: Optional custom path to INI file

    Returns:
        Path to INI file
    """
    if ini_path:
        if not os.path.exists(ini_path):
            logger.error(f"INI file not found: {ini_path}")
            sys.exit(1)
        return ini_path

    # Default to freeDView_tester.ini in the project directory
    project_path = os.path.dirname(__file__)
    default_ini = os.path.join(project_path, 'freeDView_tester.ini')
    if not os.path.exists(default_ini):
        logger.error(f"Default INI file not found: {default_ini}")
        sys.exit(1)
    return default_ini


def run_localize(args: argparse.Namespace) -> None:
    """Run Phase 1: JSON Localizer."""
    logger.info("Starting Phase 1: JSON Localizer")
    ini_path = get_ini_path(args.ini)
    try:
        json_localizer_obj = json_localizer.JsonLocalizer()
        json_localizer_obj.do_it(ini_path)
        logger.info("Phase 1 completed successfully")
    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")
        sys.exit(1)


def run_render(args: argparse.Namespace) -> None:
    """Run Phase 2: FreeDView Runner."""
    logger.info("Starting Phase 2: FreeDView Runner")
    ini_path = get_ini_path(args.ini)
    try:
        max_workers = getattr(args, 'max_workers', 4)
        freedview_runner = freeDViewRunner.FreeDViewRunner(max_workers=max_workers)
        freedview_runner.do_it(ini_path)
        logger.info("Phase 2 completed successfully")
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        sys.exit(1)


def run_compare(args: argparse.Namespace) -> None:
    """Run Phase 3: Render Compare."""
    logger.info("Starting Phase 3: Render Compare")
    ini_path = get_ini_path(args.ini)
    try:
        max_workers = getattr(args, 'max_workers', 4)
        render_compare = renderCompare.RenderCompare(ini_path, max_workers=max_workers)
        logger.info("Phase 3 completed successfully")
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        sys.exit(1)


def run_all(args: argparse.Namespace) -> None:
    """Run all phases in sequence."""
    logger.info("Starting complete pipeline: All phases")
    ini_path = get_ini_path(args.ini)

    try:
        # Phase 1: JSON Localizer
        logger.info("=" * 50)
        logger.info("Phase 1: JSON Localizer")
        logger.info("=" * 50)
        json_localizer_obj = json_localizer.JsonLocalizer()
        json_localizer_obj.do_it(ini_path)

        # Phase 2: FreeDView Runner
        logger.info("=" * 50)
        logger.info("Phase 2: FreeDView Runner")
        logger.info("=" * 50)
        max_workers = getattr(args, 'max_workers', 4)
        freedview_runner = freeDViewRunner.FreeDViewRunner(max_workers=max_workers)
        freedview_runner.do_it(ini_path)

        # Phase 3: Render Compare
        logger.info("=" * 50)
        logger.info("Phase 3: Render Compare")
        logger.info("=" * 50)
        render_compare = renderCompare.RenderCompare(ini_path, max_workers=max_workers)

        logger.info("=" * 50)
        logger.info("All phases completed successfully!")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


def run_compare_ui(args: argparse.Namespace) -> None:
    """Run comparison from UI with provided paths."""
    logger.info("Starting comparison from UI")
    
    if len(args.paths) < 5:
        logger.error("Not enough arguments. Required: folder_frame_path, "
                     "freedview_path_tester, freedview_path_orig, "
                     "freedview_name_orig, freedview_name_tester")
        sys.exit(1)

    folder_frame_path = args.paths[0]
    freedview_path_tester = args.paths[1]
    freedview_path_orig = args.paths[2]
    freedview_name_orig = args.paths[3]
    freedview_name_tester = args.paths[4]

    # Validate paths
    for path_name, path_value in [
        ("folder_frame_path", folder_frame_path),
        ("freedview_path_tester", freedview_path_tester),
        ("freedview_path_orig", freedview_path_orig)
    ]:
        if not os.path.exists(path_value):
            logger.error(f"{path_name} does not exist: {path_value}")
            sys.exit(1)

    try:
        # Collect image files
        image_orig_list = []
        image_tester_list = []

        for image_file in Path(freedview_path_orig).iterdir():
            if image_file.is_file() and image_file.suffix.lower() in ['.jpg', '.png']:
                image_orig_list.append(str(image_file))

        for image_file in Path(freedview_path_tester).iterdir():
            if image_file.is_file() and image_file.suffix.lower() in ['.jpg', '.png']:
                image_tester_list.append(str(image_file))

        image_orig_list.sort()
        image_tester_list.sort()

        # Run comparison
        render_compare = renderCompare.RenderCompare()
        render_compare.render_compare_do_it(
            folder_frame_path, image_orig_list, image_tester_list,
            freedview_path_orig, freedview_path_tester,
            freedview_name_orig, freedview_name_tester
        )

        logger.info("Comparison completed successfully")

    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='FreeDView Tester - Automated rendering comparison tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py all                    # Run all phases
  python main.py localize                # Run only Phase 1
  python main.py render                  # Run only Phase 2
  python main.py compare                 # Run only Phase 3
  python main.py compare --ui path1 path2 path3 path4 path5  # Compare from UI
        """
    )

    # Global arguments
    parser.add_argument(
        '--ini',
        type=str,
        help='Path to INI configuration file (default: freeDView_tester.ini)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum number of parallel worker threads (default: 4)'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'all' command
    all_parser = subparsers.add_parser(
        'all',
        help='Run all phases (localize, render, compare)'
    )

    # 'localize' command
    localize_parser = subparsers.add_parser(
        'localize',
        help='Run Phase 1: JSON Localizer'
    )

    # 'render' command
    render_parser = subparsers.add_parser(
        'render',
        help='Run Phase 2: FreeDView Runner'
    )

    # 'compare' command
    compare_parser = subparsers.add_parser(
        'compare',
        help='Run Phase 3: Render Compare'
    )

    # 'compare --ui' command
    compare_ui_parser = subparsers.add_parser(
        'compare-ui',
        help='Run comparison from UI with provided paths'
    )
    compare_ui_parser.add_argument(
        'paths',
        nargs='+',
        help='Paths: folder_frame_path freedview_path_tester freedview_path_orig '
             'freedview_name_orig freedview_name_tester'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Handle no command (show help)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate function
    command_handlers = {
        'all': run_all,
        'localize': run_localize,
        'render': run_render,
        'compare': run_compare,
        'compare-ui': run_compare_ui
    }

    handler = command_handlers.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

