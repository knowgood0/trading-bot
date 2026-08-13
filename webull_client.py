import os
import json
import sqlite3
import urllib.request
import urllib.error
import uuid
import time
import threading
from datetime import datetime, timezone

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


# ============================================================
# CONFIGURATION
# ============================================================

TRADE_DB = "paper_trades.db"

GOOGLE_SHEETS_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzYocjcr-9_YTeaplxao7WLF6aNWi41fDb8z3evhcBot2cy3h9QrU9Q7iePIveY9_mC"
    "/exec"
)

# SANDBOX ONLY
WEBULL_ENDPOINT = "api.sandbox.webull.com"

WEBULL_ACCOUNT_ID = "DQIO6B3HUDJB14G6GF5K0J4J7B"
WEBULL_ACCOUNT_NUMBER = "DEA73AV9"
WEBULL_ACCOUNT_NAME = "Individual Margin"


# ============================================================
# WEBULL REQUEST THROTTLING
# ============================================================

# The sandbox has been returning 429s during rapid successive
# market-data requests. Keep requests separated.
_WEBULL_REQUEST_LOCK = threading.Lock()
_LAST_WEBULL_REQUEST = 0.0

# Minimum time between Webull API requests.
WEBULL_MIN_REQUEST_INTERVAL = 2.0

# Retry delay after a 429.
WEBULL_429_RETRY_DELAY = 5.0


def _wait_for_webull_slot():
    global _LAST_WEBULL_REQUEST

    with _WEBULL_REQUEST_LOCK:

        now = time.monotonic()

        elapsed = (
            now - _LAST_WEBULL_REQUEST
        )

        if elapsed < WEBULL_MIN_REQUEST_INTERVAL:

            time.sleep(
                WEBULL_MIN_REQUEST_INTERVAL
                - elapsed
            )

        _LAST_WEBULL_REQUEST = (
            time.monotonic()
        )


def _is_rate_limit_exception(error):
    text = str(error).upper()

    return (
        "429" in text
        or "TOO_MANY_REQUESTS" in text
    )


def _webull_execute(function, *args, **kwargs):

    last_error = None

    for attempt in range(2):

        try:

            _wait_for_webull_slot()

            return function(
                *args,
                **kwargs
            )

        except Exception as e:

            last_error = e

            if (
                attempt == 0
                and _is_rate_limit_exception(e)
            ):

                time.sleep(
                    WEBULL_429_RETRY_DELAY
                )

                continue

            raise

    raise last_error


# ============================================================
# TIME / IDS
# ============================================================

def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def make_client_order_id(prefix="TV"):

    value = uuid.uuid4().hex.upper()

    return f"{prefix}{value}"[:32]


# ============================================================
# LOCAL SQLITE DATABASE
# ============================================================

def _connect_db():

    connection = sqlite3.connect(
        TRADE_DB
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


def _ensure_database():

    connection = _connect_db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            open INTEGER NOT NULL DEFAULT 0,
            contract TEXT,
            option_type TEXT,
            expiration TEXT,
            strike REAL,
            entry_price REAL,
            entry_premium REAL,
            entry_time TEXT,
            exit_price REAL,
            exit_premium REAL,
            profit_loss REAL,
            pricing_mode TEXT,
            result TEXT,
            error TEXT,
            created_at TEXT
        )
        """
    )

    connection.commit()
    connection.close()


def _row_to_dict(row):

    if row is None:
        return None

    return {
        "id": row["id"],
        "open": bool(row["open"]),
        "contract": row["contract"],
        "option_type": row["option_type"],
        "expiration": row["expiration"],
        "strike": row["strike"],
        "entry_price": row["entry_price"],
        "entry_premium": row["entry_premium"],
        "entry_time": row["entry_time"],
        "exit_price": row["exit_price"],
        "exit_premium": row["exit_premium"],
        "profit_loss": row["profit_loss"],
        "pricing_mode": row["pricing_mode"],
        "result": row["result"],
        "error": row["error"]
    }


def load_open_trade
