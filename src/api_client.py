"""OpenFDA API client for the FAERS adverse events pipeline.

Fetches adverse event reports using the Search-After pagination
pattern: an initial query built from config, then subsequent page
URLs taken from each response's Link header.
"""

import logging
import os
import time
from urllib.parse import urlencode

import requests

logger = logging.getLogger("faers_pipeline")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_reports(config):
    """Yield batches of adverse event reports from the OpenFDA API.

    Pages through results using Search-After (Link header) pagination,
    stopping when the API signals the last page or the configured
    max_records cap is reached. Each yielded batch is a list of raw
    report dicts, passed through untouched.
    """
    api_config = config["api"]
    max_records = api_config["max_records"]
    url = _build_initial_url(api_config)
    total_fetched = 0
    batch_number = 0

    logger.info(
        "Starting FAERS fetch: %d records per page, max_records=%d",
        api_config["limit"], max_records,
    )

    while url and total_fetched < max_records:
        response = _get_with_retries(
            url,
            api_config["timeout_seconds"],
            api_config["max_retries"],
            api_config["backoff_seconds"],
        )
        records = response.json().get("results", [])
        if not records:
            break

        remaining = max_records - total_fetched
        if len(records) > remaining:
            records = records[:remaining]

        batch_number += 1
        total_fetched += len(records)
        logger.info(
            "Fetched batch %d: %d records (%d total)",
            batch_number, len(records), total_fetched,
        )

        yield records
        url = _extract_next_link(response)

    logger.info(
        "Fetch complete: %d batches, %d records", batch_number, total_fetched
    )


def _build_initial_url(api_config):
    """Build the first request URL from the api section of config.

    Only the initial URL is built by us; every subsequent page URL
    is provided ready-made by the API in the Link response header.
    """
    params = {
        "search": api_config["search"],
        "sort": api_config["sort"],
        "limit": api_config["limit"],
    }
    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return f"{api_config['base_url']}?{urlencode(params)}"


def _get_with_retries(url, timeout_seconds, max_retries, backoff_seconds):
    """Execute a GET request, retrying transient failures.

    Retries network errors, timeouts, rate limiting (429), and server
    errors (5xx). Fails immediately on any other 4xx, since a bad
    request will not improve by repeating it. Raises RuntimeError
    once all attempts are exhausted.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout_seconds)
        except requests.exceptions.RequestException as exc:
            reason = f"network error: {exc}"
        else:
            if response.status_code == 200:
                return response
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
            reason = f"HTTP {response.status_code}"

        if attempt < max_retries:
            wait = backoff_seconds * attempt
            logger.warning(
                "Request attempt %d of %d failed (%s); retrying in %d seconds",
                attempt, max_retries, reason, wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"API request failed after {max_retries} attempts; last failure: {reason}"
    )


def _extract_next_link(response):
    """Return the rel="next" URL from the Link header, or None on the last page."""
    return response.links.get("next", {}).get("url")
