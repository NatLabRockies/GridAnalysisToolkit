import sys
import warnings

from loguru import logger
import os
from datetime import datetime


def is_interactive():
    """Check if the code is running in an interactive environment."""
    return hasattr(sys, 'ps1') or hasattr(sys, 'stdin') and sys.stdin.isatty()


def setup_cli_logging(log_level: str = "ERROR") -> None:
    """Configure quiet logging for CLI commands.

    By default only shows errors. Use ``--verbose`` for INFO
    or ``--debug`` for DEBUG output.
    """
    logger.remove()
    logger.add(sys.stderr, level=log_level, format="{message}")
    if log_level == "ERROR":
        warnings.filterwarnings("ignore")


def setup_logging(output_dir: str=None, log_level="INFO"):
    """
    Configure loguru logging.

    If output_dir is provided, logs will be saved to a file in that directory.
    Otherwise, logs will be printed to the console.
    """
    logger.remove()  # Remove default handler

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

                # Create a timestamped log file name
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = f"gat_report_{timestamp}.log"
        log_file_path = os.path.join(output_dir, log_file)

        logger.add(log_file_path, level=log_level, format="{time} {level} {message}", rotation="10 MB")
        logger.add(sys.stderr, level="WARNING") # Also print warnings and errors to console
        logger.info(f"Logging to file: {log_file_path}")
    elif is_interactive():
        logger.add(sys.stderr, level=log_level)
        logger.info("Interactive environment detected. Logging to console.")
    else: # non-interactive, non-file logging -> probably CLI without output dir specified yet
        logger.add(sys.stderr, level=log_level)
