"""Configure structured JSON logging for production.

JSON format when LOG_FORMAT=json (default in production).
Human-readable format in development (LOG_FORMAT=text).
"""

from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    root = logging.getLogger()
    root.setLevel(log_level)

    if root.handlers:
        return  # already configured

    if log_format == "json":
        try:
            from pythonjsonlogger.json import JsonFormatter

            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                JsonFormatter(
                    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
            root.addHandler(handler)
            return
        except ImportError:
            pass

    # Fallback: human-readable
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)-8s %(name)s  %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
