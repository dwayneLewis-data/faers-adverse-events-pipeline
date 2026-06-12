"""Live smoke test for the OpenFDA API client.

Wires the real modules together against the real API, governed by
the max_records dev cap. Run from the project root:

    python -m scripts.smoke_api_client

Not part of the unit test suite (deliberately not named test_*).
"""

from src.api_client import fetch_reports
from src.config_loader import load_config, load_env
from src.logger import get_logger


def main():
    load_env()
    config = load_config()
    logger = get_logger(config)

    total = 0
    first_record = None
    for batch in fetch_reports(config):
        if first_record is None:
            first_record = batch[0]
        total += len(batch)

    logger.info("Smoke test complete: %d records fetched", total)
    if first_record:
        logger.info("Sample record keys: %s", sorted(first_record.keys()))


if __name__ == "__main__":
    main()
