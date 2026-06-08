"""
logger.py — Pipeline run logger for FAERS Adverse Events Pipeline

Provides a configured logger instance that writes to two simultaneous destinations:
  - A timestamped log file in the logs/ directory (DEBUG and above — full detail)
  - The console/terminal (INFO and above — operational progress for human operators)

Every line written by this logger is timestamped at the moment of emission and
flushed immediately to disk. This ensures the log file accurately reflects
execution order and survives a mid-run crash without losing buffered entries.

Usage:
    from src.logger import get_logger
    logger = get_logger()
    logger.info("Pipeline started")
    logger.debug("Raw API response code: 200")
    logger.error("Failed to connect to database")
"""

import logging
import os
from datetime import datetime


def get_logger(config: dict = None) -> logging.Logger:
    """
    Build and return a configured logger for a single pipeline run.

    Creates a timestamped log file in the configured logs directory and
    attaches a console handler for live operator visibility. Both handlers
    share the same format so log entries look identical regardless of
    where they appear.

    Args:
        config: The loaded pipeline config dictionary from config_loader.
                If None, falls back to defaults (logs/ directory, INFO level).

    Returns:
        A fully configured logging.Logger instance ready for use.
    """

    # ------------------------------------------------------------------ #
    # 1. Resolve configuration values — use config if provided,           #
    #    fall back to safe defaults if called without config               #
    # ------------------------------------------------------------------ #
    if config is not None:
        log_path = config.get("logging", {}).get("log_path", "logs")
        log_level_str = config.get("logging", {}).get("log_level", "INFO")
    else:
        log_path = "logs"
        log_level_str = "INFO"

    # Convert the level string from config ("DEBUG", "INFO", etc.)
    # to the integer constant Python's logging module expects.
    # logging.getLevelName() handles this translation — "INFO" becomes 20,
    # "DEBUG" becomes 10, and so on.
    log_level = logging.getLevelName(log_level_str.upper())

    # ------------------------------------------------------------------ #
    # 2. Build the timestamped log filename                                #
    # ------------------------------------------------------------------ #
    # Format: pipeline_YYYYMMDD_HHMMSS.log
    # One file per run. Timestamp is generated at logger creation time,
    # which is pipeline start time.
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"pipeline_{run_timestamp}.log"
    log_filepath = os.path.join(log_path, log_filename)

    # ------------------------------------------------------------------ #
    # 3. Ensure the logs directory exists                                  #
    # ------------------------------------------------------------------ #
    # exist_ok=True means no error is raised if the directory already
    # exists. This is safe to call on every run.
    os.makedirs(log_path, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 4. Define the log line format                                        #
    # ------------------------------------------------------------------ #
    # Format: 2026-06-08 14:30:22 | INFO     | Message text here
    #
    # - Timestamp first — every line sortable by time
    # - Pipe delimiters — makes log output grep-friendly
    # - %-8s on levelname — pads to 8 characters so severity columns
    #   align visually (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # ------------------------------------------------------------------ #
    # 5. Build the FILE handler — DEBUG and above, immediate flush         #
    # ------------------------------------------------------------------ #
    # The file handler captures everything — DEBUG through CRITICAL.
    # This is the forensic record: every API call, every batch count,
    # every config value, every error.
    #
    # delay=False opens the file immediately at handler creation rather
    # than waiting for the first log entry. This ensures the log file
    # exists from pipeline start, even if the first message is delayed.
    file_handler = logging.FileHandler(
        filename=log_filepath,
        mode="a",           # append — safe default, though each run gets its own file
        encoding="utf-8",
        delay=False,        # open immediately — do not wait for first write
    )
    file_handler.setLevel(logging.DEBUG)    # capture everything in the file
    file_handler.setFormatter(formatter)

    # ------------------------------------------------------------------ #
    # 6. Build the CONSOLE handler — INFO and above                        #
    # ------------------------------------------------------------------ #
    # The console handler is the live operator view. It shows progress,
    # row counts, stage completions, warnings, and errors — enough for a
    # human watching the run to know the pipeline is moving and healthy.
    # DEBUG-level detail stays out of the console; it lives in the file.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # INFO and above to console
    console_handler.setFormatter(formatter)

    # ------------------------------------------------------------------ #
    # 7. Assemble the logger                                               #
    # ------------------------------------------------------------------ #
    # Using a named logger ("faers_pipeline") rather than the root logger.
    # This avoids accidentally capturing log output from third-party
    # libraries (requests, SQLAlchemy, etc.) that also use Python logging.
    logger = logging.getLogger("faers_pipeline")
    logger.setLevel(logging.DEBUG)  # logger itself accepts everything;
                                    # handlers above filter by their own levels

    # Guard against duplicate handlers if get_logger() is called more than
    # once in the same Python process (e.g., during testing).
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # ------------------------------------------------------------------ #
    # 8. Emit the opening log entry                                        #
    # ------------------------------------------------------------------ #
    logger.info(f"Logger initialized — log file: {log_filepath}")

    return logger