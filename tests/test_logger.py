"""
test_logger.py — Unit tests for src/logger.py

Tests verify that get_logger() produces a correctly configured logger:
  - Returns a Logger instance
  - Attaches exactly two handlers (file and console)
  - File handler is set to DEBUG level
  - Console handler is set to INFO level
  - Log file is created in the configured logs directory
  - Duplicate handler guard works — calling get_logger() twice does not
    double up handlers
  - Fallback behavior works when no config is passed

These tests do not assert the content of log messages or test Python's
logging infrastructure itself — only the configuration this module applies.
"""

import logging
import os
import tempfile
import pytest

from src.logger import get_logger


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def make_config(log_path: str, log_level: str = "DEBUG") -> dict:
    """
    Build a minimal config dictionary suitable for passing to get_logger().
    Uses a caller-supplied log_path so tests can direct output to a
    temporary directory rather than the real logs/ folder.
    """
    return {
        "logging": {
            "log_path": log_path,
            "log_level": log_level,
        }
    }


def reset_logger():
    """
    Remove all handlers from the named logger and reset its level.

    Python's logging module keeps named loggers alive for the entire process
    lifetime. Without this reset between tests, handlers accumulate across
    test functions and the duplicate guard will prevent new handlers from
    being added — causing tests to interfere with each other.
    """
    logger = logging.getLogger("faers_pipeline")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def clean_logger():
    """
    Automatically reset the named logger before every test in this module.
    autouse=True means this fixture runs without being explicitly requested —
    every test function gets a clean logger state.
    """
    reset_logger()
    yield
    reset_logger()


@pytest.fixture()
def tmp_log_dir(tmp_path):
    """
    Provide a temporary directory for log file output.
    pytest's built-in tmp_path fixture creates a unique temp directory
    per test run and cleans it up automatically afterward.
    """
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return str(log_dir)


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

def test_get_logger_returns_logger_instance(tmp_log_dir):
    """get_logger() should return a logging.Logger object."""
    config = make_config(tmp_log_dir)
    logger = get_logger(config)
    assert isinstance(logger, logging.Logger)


def test_logger_has_exactly_two_handlers(tmp_log_dir):
    """
    get_logger() should attach exactly two handlers:
    one file handler and one console (stream) handler.
    """
    config = make_config(tmp_log_dir)
    logger = get_logger(config)
    assert len(logger.handlers) == 2


def test_file_handler_level_is_debug(tmp_log_dir):
    """
    The file handler should be set to DEBUG level so that all
    messages are captured in the log file for forensic purposes.
    """
    config = make_config(tmp_log_dir)
    logger = get_logger(config)

    file_handlers = [
        h for h in logger.handlers
        if isinstance(h, logging.FileHandler)
    ]

    assert len(file_handlers) == 1
    assert file_handlers[0].level == logging.DEBUG


def test_console_handler_level_is_info(tmp_log_dir):
    """
    The console handler should be set to INFO level so that
    DEBUG-level detail stays out of the operator's terminal view.
    """
    config = make_config(tmp_log_dir)
    logger = get_logger(config)

    console_handlers = [
        h for h in logger.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
    ]

    assert len(console_handlers) == 1
    assert console_handlers[0].level == logging.INFO


def test_log_file_is_created(tmp_log_dir):
    """
    Calling get_logger() should create a log file in the
    configured logs directory. The file should exist on disk
    immediately after logger initialization.
    """
    config = make_config(tmp_log_dir)
    get_logger(config)

    log_files = os.listdir(tmp_log_dir)
    assert len(log_files) == 1
    assert log_files[0].startswith("pipeline_")
    assert log_files[0].endswith(".log")


def test_log_filename_contains_timestamp(tmp_log_dir):
    """
    The log filename should follow the pattern pipeline_YYYYMMDD_HHMMSS.log.
    Verify the filename has the right structure without asserting the
    exact timestamp value, which would make the test time-dependent.
    """
    config = make_config(tmp_log_dir)
    get_logger(config)

    log_files = os.listdir(tmp_log_dir)
    filename = log_files[0]

    # Strip prefix and suffix, leaving YYYYMMDD_HHMMSS
    stem = filename.replace("pipeline_", "").replace(".log", "")
    parts = stem.split("_")

    assert len(parts) == 2, f"Expected 2 timestamp parts, got: {parts}"
    assert len(parts[0]) == 8, f"Expected 8-digit date, got: {parts[0]}"   # YYYYMMDD
    assert len(parts[1]) == 6, f"Expected 6-digit time, got: {parts[1]}"   # HHMMSS
    assert parts[0].isdigit(), f"Date part should be numeric, got: {parts[0]}"
    assert parts[1].isdigit(), f"Time part should be numeric, got: {parts[1]}"


def test_duplicate_handler_guard(tmp_log_dir):
    """
    Calling get_logger() twice in the same process should not result
    in duplicate handlers. The guard in logger.py should prevent a
    second set of handlers from being added.
    """
    config = make_config(tmp_log_dir)
    get_logger(config)
    get_logger(config)

    logger = logging.getLogger("faers_pipeline")
    assert len(logger.handlers) == 2


def test_fallback_when_no_config_passed(tmp_path):
    """
    get_logger() called with no arguments should not raise an exception.
    It should fall back to default values (logs/ directory, INFO level)
    and return a functioning logger.

    Note: this test allows get_logger() to use its default log_path of
    'logs/' relative to wherever the test is run from. We verify only
    that it returns a Logger — not the specific file location — since
    the default path is outside our temp directory control.
    """
    logger = get_logger()
    assert isinstance(logger, logging.Logger)