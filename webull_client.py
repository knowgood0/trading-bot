import os
import json
import sqlite3
import urllib.request
import uuid
import time
import threading
import logging
from datetime import datetime, timezone

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


TRADE_DB = "paper_trades.db"

GOOGLE_SHEETS_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzYocjcr-9_YTeaplxao7WLF6aNWi41fDb8z3evhcBot2cy3h9QrU9Q7iePIveY9_mC"
    "/exec"
)

# ============================================================
# PAPER / SANDBOX ONLY
# ============================================================

WEBULL_ENDPOINT = "api.sandbox.webull.com"
WEBULL_ACCOUNT_ID = "DQIO6B3HUDJB14G6GF5K0J4J7B"
WEBULL_ACCOUNT_NUMBER = "DEA73AV9"
WEBULL_ACCOUNT_NAME = "Individual Margin"
WEBULL_ENVIRONMENT = "SANDBOX"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webull request throttling / caching
# ---------------------------------------------------------------------------

_REQUEST_LOCK = threading.Lock()
_LAST_WEBULL_REQUEST = 0.0
_MIN_WEBULL_REQUEST_INTERVAL = 1.10

_SPY_CACHE = {"price": None, "time": 0.0}
_SPY_CACHE_SECONDS = 2.5


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_client_order_id(prefix="TV"):
    # Webull maximum is 32 characters.
    return f"{prefix}{uuid.uuid4().hex.upper()}"[:32]


def _throttle_webull():
    global _LAST_WEBULL_REQUEST

    with _REQUEST_LOCK:
        now = time.monotonic()
        wait = _MIN_WEBULL_REQUEST_INTERVAL - (
            now - _LAST_WEBULL_REQUEST
        )

        if wait > 0:
            time.sleep(wait)

        _LAST_WEBULL_REQUEST = time.monotonic()


def _webull_call(fn, *args, **kwargs):
    """Serialize SDK calls and retry sandbox 429 responses."""
    last_error = None

    for attempt in range(3):
        try:
            _throttle_webull()
            return fn(*args, **kwargs)

        except Exception as e:
            last_error = e
            text = str(e)

            if "TOO_MANY_REQUESTS" not in text and "429" not in text:
                raise

            time.sleep(2.0 * (attempt + 1))

    raise last_error


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

def _connect_db():
    connection = sqlite3.connect(TRADE_DB)
    connection.row_factory = sqlite3.Row
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
        "error": row["error"],
    }


# ---------------------------------------------------------------------------
# Google Sheets journal
# ---------------------------------------------------------------------------

def send_to_google_sheets(data):
    """Best-effort journal. It must never block or fail a trade request."""
    try:
        payload = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(
            GOOGLE_SHEETS_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TradingBot/7.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read().decode("utf-8")

        try:
            return json.loads(body)
        except Exception:
            return {"success": True, "response": body}

    except Exception as e:
        logger.warning(
            "Google Sheets journal failed (non-blocking): %s",
            e,
        )
        return {
            "success": False,
            "error": str(e),
            "non_blocking": True,
        }


def get_open_trade_from_google_sheets():
    try:
        request = urllib.request.Request(
            GOOGLE_SHEETS_URL + "?action=get_open_trade",
            headers={"User-Agent": "TradingBot/7.0"},
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=3) as response:
            result = json.loads(response.read().decode("utf-8"))

        if not result.get("success"):
            return None

        return result.get("trade") or None

    except Exception as e:
        logger.warning(
            "Google Sheets open-trade lookup failed; "
            "falling back to SQLite: %s",
            e,
        )
        return None


def update_google_trade_closed(
    contract,
    exit_price,
    exit_premium,
    profit_loss,
    pricing_mode,
    result="CLOSED",
    error="",
):
    return send_to_google_sheets(
        {
            "action": "close_trade",
            "contract": contract,
            "exit_price": exit_price,
            "exit_premium": exit_premium,
            "profit_loss": profit_loss,
            "pricing_mode": pricing_mode,
            "result": result,
            "error": error,
            "timestamp": utc_now(),
        }
    )


def journal_trade(
    event,
    action="",
    symbol="SPY",
    option_type="",
    contract="",
    expiration="",
    strike=None,
    spy_price=None,
    option_premium=None,
    entry_price=None,
    exit_price=None,
    profit_loss=None,
    pricing_mode="",
    result="",
    error="",
):
    return send_to_google_sheets(
        {
            "timestamp": utc_now(),
            "event": event,
            "action": action,
            "symbol": symbol,
            "option_type": option_type,
            "contract": contract,
            "expiration": expiration,
            "strike": strike,
            "spy_price": spy_price,
            "option_premium": option_premium,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "profit_loss": profit_loss,
            "pricing_mode": pricing_mode,
            "result": result,
            "error": error,
        }
    )


# ---------------------------------------------------------------------------
# Local trade persistence
# ---------------------------------------------------------------------------

def load_open_trade():
    google_trade = get_open_trade_from_google_sheets()

    if google_trade:
        logger.info(
            "Open trade source: Google Sheets; contract=%s",
            google_trade.get("contract"),
        )
        return google_trade

    _ensure_database()

    connection = _connect_db()
    row = connection.execute(
        """
        SELECT *
        FROM paper_trades
        WHERE open = 1
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    connection.close()

    local_trade = _row_to_dict(row)

    if local_trade:
        logger.info(
            "Open trade source: SQLite; contract=%s",
            local_trade.get("contract"),
        )

    return local_trade


def load_latest_trade():
    _ensure_database()

    connection = _connect_db()
    row = connection.execute(
        """
        SELECT *
        FROM paper_trades
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    connection.close()

    return _row_to_dict(row)


def save_trade(trade):
    _ensure_database()

    connection = _connect_db()

    connection.execute(
        """
        INSERT INTO paper_trades (
            open,
            contract,
            option_type,
            expiration,
            strike,
            entry_price,
            entry_premium,
            entry_time,
            exit_price,
            exit_premium,
            profit_loss,
            pricing_mode,
            result,
            error,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1 if trade.get("open") else 0,
            trade.get("contract"),
            trade.get("option_type"),
            trade.get("expiration"),
            trade.get("strike"),
            trade.get("entry_price"),
            trade.get("entry_premium"),
            trade.get("entry_time"),
            trade.get("exit_price"),
            trade.get("exit_premium"),
            trade.get("profit_loss"),
            trade.get("pricing_mode"),
            trade.get("result"),
            trade.get("error"),
            utc_now(),
        ),
    )

    connection.commit()

    trade["id"] = connection.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    connection.close()


def close_trade(
    trade_id,
    exit_price,
    exit_premium,
    profit_loss,
    pricing_mode,
):
    _ensure_database()

    connection = _connect_db()

    connection.execute(
        """
        UPDATE paper_trades
        SET
            open = 0,
            exit_price = ?,
            exit_premium = ?,
            profit_loss = ?,
            pricing_mode = ?,
            result = 'CLOSED'
        WHERE id = ?
        """,
        (
            exit_price,
            exit_premium,
            profit_loss,
            pricing_mode,
            trade_id,
        ),
    )

    connection.commit()
    connection.close()


def get_trade_history(limit=50):
    _ensure_database()

    connection = _connect_db()

    rows = connection.execute(
        """
        SELECT *
        FROM paper_trades
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    connection.close()

    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Webull clients / account
# ---------------------------------------------------------------------------

def get_clients():
    """
    SINGLE centralized Webull client factory.

    Both direct Flask endpoints and TradingView webhook execution ultimately
    call the same trading functions, which call this same client factory.

    Sandbox endpoint is explicitly fixed here. No live endpoint is permitted.
    """
    app_key = os.environ.get("WEBULL_APP_KEY")
    app_secret = os.environ.get("WEBULL_APP_SECRET")

    if not app_key:
        raise RuntimeError(
            "WEBULL_APP_KEY environment variable is missing"
        )

    if not app_secret:
        raise RuntimeError(
            "WEBULL_APP_SECRET environment variable is missing"
        )

    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", WEBULL_ENDPOINT)

    logger.info(
        "Webull client initialized: environment=%s endpoint=%s "
        "account_id=%s",
        WEBULL_ENVIRONMENT,
        WEBULL_ENDPOINT,
        WEBULL_ACCOUNT_ID,
    )

    return TradeClient(api_client), DataClient(api_client)


def resolve_account():
    return {
        "account_id": WEBULL_ACCOUNT_ID,
        "account_number": WEBULL_ACCOUNT_NUMBER,
        "account_name": WEBULL_ACCOUNT_NAME,
        "environment": WEBULL_ENVIRONMENT,
        "endpoint": WEBULL_ENDPOINT,
    }


def test_webull_connection():
    try:
        trade_client, _ = get_clients()

        response = _webull_call(
            trade_client.account_v2.get_account_list
        )

        return {
            "success": True,
            "status_code": response.status_code,
            "account": response.json(),
            "configured_account": resolve_account(),
            "environment": WEBULL_ENVIRONMENT,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "configured_account": resolve_account(),
            "environment": WEBULL_ENVIRONMENT,
        }


def _query_account(account_id, account_name):
    result = {
        "account_name": account_name,
        "account_id": account_id,
        "balance": None,
        "positions": None,
        "balance_status": None,
        "positions_status": None,
        "errors": [],
    }

    try:
        trade_client, _ = get_clients()

        try:
            response = _webull_call(
                trade_client.account_v2.get_account_balance,
                account_id,
            )
            result["balance_status"] = response.status_code
            result["balance"] = response.json()
        except Exception as e:
            result["errors"].append("BALANCE: " + str(e))

        try:
            response = _webull_call(
                trade_client.account_v2.get_account_position,
                account_id,
            )
            result["positions_status"] = response.status_code
            result["positions"] = response.json()
        except Exception as e:
            result["errors"].append("POSITIONS: " + str(e))

    except Exception as e:
        result["errors"].append("CLIENT: " + str(e))

    result["success"] = (
        result["balance_status"] == 200
        and result["positions_status"] == 200
    )

    return result


def account_diagnostic():
    diagnostic = {
        "success": False,
        "environment": WEBULL_ENVIRONMENT,
        "endpoint": WEBULL_ENDPOINT,
        "configured_account": resolve_account(),
        "accounts": {},
        "account_list": None,
        "account_list_status": None,
        "error": None,
    }

    try:
        trade_client, _ = get_clients()

        try:
            response = _webull_call(
                trade_client.account_v2.get_account_list
            )
            diagnostic["account_list_status"] = response.status_code
            diagnostic["account_list"] = response.json()

        except Exception as e:
            diagnostic["error"] = "ACCOUNT LIST: " + str(e)

        configured = _query_account(
            WEBULL_ACCOUNT_ID,
            WEBULL_ACCOUNT_NAME,
        )

        diagnostic["accounts"]["configured"] = configured
        diagnostic["success"] = configured.get("success", False)

    except Exception as e:
        diagnostic["error"] = str(e)

    return diagnostic


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def get_webull_positions():
    try:
        trade_client, _ = get_clients()

        response = _webull_call(
            trade_client.account_v2.get_account_position,
            WEBULL_ACCOUNT_ID,
        )

        return {
            "success": True,
            "status_code": response.status_code,
            "account": resolve_account(),
            "positions": response.json(),
        }

    except Exception as e:
        return {
            "success": False,
            "account": resolve_account(),
            "error": str(e),
        }


def get_webull_option_position(option_symbol):
    result = get_webull_positions()

    if not result.get("success"):
        return result

    positions = result.get("positions")

    if isinstance(positions, dict):
        for key in ("positions", "data", "items"):
            if isinstance(positions.get(key), list):
                positions = positions[key]
                break

    if not isinstance(positions, list):
        return {
            "success": True,
            "found": False,
            "symbol": option_symbol,
            "positions_response": result,
        }

    matches = []

    for position in positions:
        if not isinstance(position, dict):
            continue

        if str(position.get("symbol") or "") == option_symbol:
            matches.append(position)
            continue

        for leg in position.get("legs") or []:
            if (
                isinstance(leg, dict)
                and str(leg.get("symbol") or "") == option_symbol
            ):
                matches.append(position)
                break

    return {
        "success": True,
        "found": bool(matches),
        "symbol": option_symbol,
        "positions": matches,
    }


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------

def get_spy_price():
    now = time.monotonic()

    if (
        _SPY_CACHE["price"] is not None
        and now - _SPY_CACHE["time"] < _SPY_CACHE_SECONDS
    ):
        logger.info(
            "SPY price: %.4f (cached)",
            _SPY_CACHE["price"],
        )

        return {
            "success": True,
            "data": {
                "price": _SPY_CACHE["price"],
                "cached": True,
            },
        }

    try:
        _, data_client = get_clients()

        response = _webull_call(
            data_client.market_data.get_snapshot,
            "SPY",
            Category.US_STOCK.name,
        )

        data = response.json()
        price = None

        if isinstance(data, list) and data:
            price = data[0].get("price")

        elif isinstance(data, dict):
            price = data.get("price")

        if price is not None:
            _SPY_CACHE["price"] = float(price)
            _SPY_CACHE["time"] = time.monotonic()

        logger.info("SPY price response received: price=%s", price)

        return {
            "success": True,
            "data": data,
        }

    except Exception as e:
        logger.exception("SPY price lookup failed")
        return {
            "success": False,
            "error": str(e),
        }


def extract_spy_price():
    result = get_spy_price()

    if not result.get("success"):
        return None

    data = result.get("data")

    try:
        if isinstance(data, list) and data:
            return float(data[0]["price"])

        if isinstance(data, dict):
            return float(data["price"])

    except Exception:
        return None

    return None


def get_option_contracts(option_type="CALL"):
    try:
        _, data_client = get_clients()

        normalized_type = str(option_type).strip().upper()

        if normalized_type not in ("CALL", "PUT"):
            return {
                "error": "Invalid option type: " + normalized_type
            }

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logger.info(
            "Option chain lookup: symbol=SPY type=%s expiration=%s "
            "style=AMERICAN",
            normalized_type,
            today,
        )

        response = _webull_call(
            data_client.instrument.get_option_contracts,
            category=Category.US_OPTION.name,
            underlying_symbols="SPY",
            status="LISTING",
            start_date=today,
            end_date=today,
            option_type=normalized_type,
            style="AMERICAN",
            page_size=1000,
        )

        result = response.json()

        if isinstance(result, dict):
            if isinstance(result.get("data"), list):
                return result["data"]

            if isinstance(result.get("items"), list):
                return result["items"]

        return result

    except Exception as e:
        logger.exception("Option contract lookup failed")
        return {"error": str(e)}


def _select_contract_with_spy_price(option_type, spy_price):
    try:
        normalized_type = str(option_type).strip().upper()

        if normalized_type not in ("CALL", "PUT"):
            return {
                "success": False,
                "error": "Option type must be CALL or PUT",
            }

        if spy_price is None:
            return {
                "success": False,
                "error": "SPY price is required",
            }

        contracts = get_option_contracts(normalized_type)

        if isinstance(contracts, dict) and "error" in contracts:
            return {
                "success": False,
                "error": contracts["error"],
            }

        if not isinstance(contracts, list):
            return {
                "success": False,
                "error": "Unexpected option contract response",
            }

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        valid = []

        for contract in contracts:
            try:
                expiration = str(
                    contract.get("expiration_date")
                    or contract.get("expiration")
                    or ""
                )[:10]

                strike_value = contract.get("strike_price")

                if strike_value is None:
                    continue

                strike = float(strike_value)

                contract_type = str(
                    contract.get("option_type") or ""
                ).upper()

                def_type = str(
                    contract.get("def_type") or ""
                ).upper()

                style = str(
                    contract.get("style") or ""
                ).upper()

                tradable_status = str(
                    contract.get("tradable_status") or ""
                ).upper()

                if (
                    def_type == "STANDARD"
                    and style == "AMERICAN"
                    and tradable_status == "OC"
                    and contract_type == normalized_type
                    and expiration == today
                ):
                    valid.append(contract)

            except Exception:
                continue

        logger.info(
            "Contract selection: type=%s spy_price=%.4f "
            "today=%s valid_contracts=%d",
            normalized_type,
            float(spy_price),
            today,
            len(valid),
        )

        if not valid:
            return {
                "success": False,
                "error": (
                    f"No valid 0DTE {normalized_type} "
                    "contracts found for today"
                ),
            }

        valid.sort(
            key=lambda x: abs(
                float(x["strike_price"]) - float(spy_price)
            )
        )

        selected = valid[0]

        selected_result = {
            "symbol": selected.get("symbol"),
            "underlying_symbol": selected.get(
                "underlying_symbol",
                "SPY",
            ),
            "type": normalized_type,
            "strike": selected.get("strike_price"),
            "expiration": (
                selected.get("expiration_date")
                or selected.get("expiration")
            ),
            "instrument_id": selected.get("instrument_id"),
            "underlying_instrument_id": selected.get(
                "underlying_instrument_id"
            ),
            "raw": selected,
        }

        logger.info(
            "Selected contract: symbol=%s strike=%s expiration=%s "
            "option_type=%s",
            selected_result["symbol"],
            selected_result["strike"],
            selected_result["expiration"],
            selected_result["type"],
        )

        return {
            "success": True,
            "spy_price": float(spy_price),
            "selected_contract": selected_result,
        }

    except Exception as e:
        logger.exception("Contract selection failed")
        return {
            "success": False,
            "error": str(e),
        }


def select_0dte_atm_contract(option_type="CALL"):
    spy_price = extract_spy_price()

    if spy_price is None:
        return {
            "success": False,
            "error": "Unable to get current SPY price",
        }

    return _select_contract_with_spy_price(
        option_type,
        spy_price,
    )


def select_contract(option_type="CALL"):
    return select_0dte_atm_contract(option_type)


def get_option_price(option_symbol):
    try:
        _, data_client = get_clients()

        logger.info(
            "Option premium lookup: contract=%s",
            option_symbol,
        )

        response = _webull_call(
            data_client.option_market_data.get_option_snapshot,
            option_symbol,
            Category.US_OPTION.name,
        )

        data = response.json()

        item = (
            data[0]
            if isinstance(data, list) and data
            else data
            if isinstance(data, dict)
            else {}
        )

        premium = None

        for field in (
            "price",
            "latest_price",
            "last_price",
            "last",
            "close",
            "mark_price",
        ):
            if item.get(field) is not None:
                premium = float(item[field])
                break

        logger.info(
            "Option premium result: contract=%s premium=%s",
            option_symbol,
            premium,
        )

        return {
            "success": True,
            "premium": premium,
            "data": data,
        }

    except Exception as e:
        logger.exception(
            "Option premium lookup failed for %s",
            option_symbol,
        )

        return {
            "success": False,
            "premium": None,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Webull option orders
# ---------------------------------------------------------------------------

def _webull_place_option_order(
    option_symbol,
    option_type,
    side,
    quantity,
    limit_price,
    strike_price,
    expiration,
    underlying_symbol="SPY",
):
    """
    Common Webull Sandbox OPTION_V2 order mechanism.

    The OCC option symbol is used for market data and tracking.

    The order leg's symbol MUST be the underlying symbol, e.g. SPY.
    """
    try:
        trade_client, _ = get_clients()

        normalized_type = str(option_type).strip().upper()
        normalized_side = str(side).strip().upper()

        if normalized_type not in ("CALL", "PUT"):
            return {
                "success": False,
                "error": "Invalid option type",
            }

        if normalized_side not in ("BUY", "SELL"):
            return {
                "success": False,
                "error": "Invalid option side",
            }

        if limit_price is None:
            return {
                "success": False,
                "error": "Missing option limit price",
            }

        if strike_price is None or expiration is None:
            return {
                "success": False,
                "error": "Missing option strike or expiration",
            }

        if not underlying_symbol:
            underlying_symbol = "SPY"

        client_order_id = make_client_order_id("TV")

        option_order = {
            "client_order_id": client_order_id,
            "combo_type": "NORMAL",
            "order_type": "LIMIT",
            "quantity": str(int(quantity)),
            "limit_price": f"{float(limit_price):.2f}",
            "option_strategy": "SINGLE",
            "side": normalized_side,
            "time_in_force": "DAY",
            "entrust_type": "QTY",
            "legs": [
                {
                    "side": normalized_side,
                    "quantity": str(int(quantity)),
                    "symbol": str(underlying_symbol).upper(),
                    "strike_price": f"{float(strike_price):.2f}",
                    "option_expire_date": str(expiration)[:10],
                    "instrument_type": "OPTION",
                    "option_type": normalized_type,
                    "market": "US",
                }
            ],
        }

        logger.info(
            "Submitting Webull Sandbox OPTION_V2 %s: account_id=%s "
            "endpoint=%s contract=%s underlying=%s strike=%s "
            "expiration=%s option_type=%s limit_price=%s quantity=%s",
            normalized_side,
            WEBULL_ACCOUNT_ID,
            WEBULL_ENDPOINT,
            option_symbol,
            str(underlying_symbol).upper(),
            strike_price,
            str(expiration)[:10],
            normalized_type,
            f"{float(limit_price):.2f}",
            quantity,
        )

        response = _webull_call(
            trade_client.order_v2.place_option,
            WEBULL_ACCOUNT_ID,
            [option_order],
        )

        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": str(response)}

        success = 200 <= response.status_code < 300

        logger.info(
            "Webull Sandbox OPTION_V2 result: success=%s status=%s "
            "contract=%s client_order_id=%s",
            success,
            response.status_code,
            option_symbol,
            client_order_id,
        )

        if not success:
            logger.error(
                "Webull Sandbox OPTION_V2 order failed: "
                "status=%s response=%s",
                response.status_code,
                response_data,
            )

        return {
            "success": success,
            "status_code": response.status_code,
            "client_order_id": client_order_id,
            "account": resolve_account(),
            "order_endpoint": "OPTION_V2",
            "option_symbol": option_symbol,
            "underlying_symbol": str(underlying_symbol).upper(),
            "response": response_data,
            "prepared_order": option_order,
            "order_status": _extract_order_status(response_data),
        }

    except Exception as e:
        logger.exception(
            "Webull Sandbox OPTION_V2 order exception: "
            "side=%s contract=%s",
            side,
            option_symbol,
        )

        return {
            "success": False,
            "account": resolve_account(),
            "error": str(e),
        }


def _extract_order_status(data):
    if not isinstance(data, dict):
        return None

    for key in (
        "status",
        "order_status",
        "orderStatus",
        "state",
    ):
        value = data.get(key)

        if value not in (None, ""):
            return value

    for key in (
        "order",
        "data",
        "result",
    ):
        nested = data.get(key)

        if isinstance(nested, dict):
            found = _extract_order_status(nested)
            if found is not None:
                return found

        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    found = _extract_order_status(item)
                    if found is not None:
                        return found

    return None


def test_order_detail(client_order_id):
    try:
        trade_client, _ = get_clients()

        response = _webull_call(
            trade_client.order_v2.get_order_detail,
            WEBULL_ACCOUNT_ID,
            client_order_id,
        )

        data = response.json()

        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "account": resolve_account(),
            "order": data,
            "order_status": _extract_order_status(data),
        }

    except Exception as e:
        return {
            "success": False,
            "account": resolve_account(),
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------

def paper_buy_spy(option_type="CALL"):
    normalized_type = str(option_type).strip().upper()

    logger.info(
        "PAPER BUY START: option_type=%s account_id=%s "
        "environment=%s endpoint=%s",
        normalized_type,
        WEBULL_ACCOUNT_ID,
        WEBULL_ENVIRONMENT,
        WEBULL_ENDPOINT,
    )

    if normalized_type not in ("CALL", "PUT"):
        return {
            "success": False,
            "error": "Option type must be CALL or PUT",
        }

    existing_trade = load_open_trade()

    if existing_trade:
        logger.warning(
            "PAPER BUY blocked: existing open trade contract=%s",
            existing_trade.get("contract"),
        )

        return {
            "success": False,
            "error": "A logged paper trade is already open.",
            "trade": existing_trade,
        }

    spy_price = extract_spy_price()

    if spy_price is None:
        error = "Unable to get current SPY price"

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            result="FAILED",
            error=error,
        )

        return {
            "success": False,
            "error": error,
        }

    logger.info(
        "PAPER BUY SPY PRICE: %.4f",
        spy_price,
    )

    contract_result = _select_contract_with_spy_price(
        normalized_type,
        spy_price,
    )

    if not contract_result.get("success"):
        error = contract_result.get(
            "error",
            "Contract selection failed",
        )

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            spy_price=spy_price,
            result="FAILED",
            error=error,
        )

        return contract_result

    selected = contract_result["selected_contract"]

    contract_symbol = selected.get("symbol")
    underlying_symbol = selected.get(
        "underlying_symbol",
        "SPY",
    )
    expiration = selected.get("expiration")
    strike = selected.get("strike")

    logger.info(
        "PAPER BUY CONTRACT: symbol=%s strike=%s expiration=%s "
        "option_type=%s",
        contract_symbol,
        strike,
        expiration,
        normalized_type,
    )

    if not contract_symbol or strike is None or expiration is None:
        error = (
            "Selected option is missing "
            "symbol, strike, or expiration"
        )

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            spy_price=spy_price,
            result="FAILED",
            error=error,
        )

        return {
            "success": False,
            "error": error,
        }

    premium_result = get_option_price(contract_symbol)
    entry_premium = premium_result.get("premium")

    logger.info(
        "PAPER BUY PREMIUM: contract=%s premium=%s",
        contract_symbol,
        entry_premium,
    )

    if entry_premium is None:
        error = (
            "Unable to obtain option premium. "
            "No Webull order submitted."
        )

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            contract=contract_symbol,
            expiration=expiration,
            strike=strike,
            spy_price=spy_price,
            result="FAILED",
            error=error,
        )

        return {
            "success": False,
            "error": error,
            "contract": contract_symbol,
            "premium": premium_result,
        }

    order_result = _webull_place_option_order(
        option_symbol=contract_symbol,
        option_type=normalized_type,
        side="BUY",
        quantity=1,
        limit_price=entry_premium,
        strike_price=strike,
        expiration=expiration,
        underlying_symbol=underlying_symbol,
    )

    if not order_result.get("success"):
        error = str(
            order_result.get("response")
            or order_result.get("error")
            or "Webull BUY failed"
        )

        logger.error(
            "PAPER BUY FAILED at Webull: contract=%s error=%s",
            contract_symbol,
            error,
        )

        journal_trade(
            event="WEBULL_BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            contract=contract_symbol,
            expiration=expiration,
            strike=strike,
            spy_price=spy_price,
            option_premium=entry_premium,
            result="FAILED",
            error=error,
        )

        return {
            "success": False,
            "message": "Webull Sandbox LIMIT BUY was NOT accepted",
            "contract": contract_symbol,
            "premium": entry_premium,
            "order": order_result,
        }

    entry_time = utc_now()

    actual_webull_status = (
        order_result.get("order_status")
        or "ACCEPTED"
    )

    trade = {
        "open": True,
        "contract": contract_symbol,
        "option_type": normalized_type,
        "expiration": expiration,
        "strike": strike,
        "entry_price": spy_price,
        "entry_premium": entry_premium,
        "entry_time": entry_time,
        "exit_price": None,
        "exit_premium": None,
        "profit_loss": None,
        "pricing_mode": "OPTION_PREMIUM",
        "result": "OPEN",
        "error": None,
        "order_status": actual_webull_status,
        "client_order_id": order_result.get("client_order_id"),
    }

    # Only now, after Webull accepted the order, create local open state.
    save_trade(trade)

    google_result = journal_trade(
        event="WEBULL_BUY",
        action="BUY",
        symbol="SPY",
        option_type=normalized_type,
        contract=contract_symbol,
        expiration=expiration,
        strike=strike,
        spy_price=spy_price,
        option_premium=entry_premium,
        entry_price=spy_price,
        pricing_mode="OPTION_PREMIUM",
        result="OPEN",
        error="",
    )

    logger.info(
        "PAPER BUY ACCEPTED: contract=%s client_order_id=%s "
        "status=%s local_trade_created=True",
        contract_symbol,
        order_result.get("client_order_id"),
        actual_webull_status,
    )

    return {
        "success": True,
        "message": (
            "Webull Sandbox LIMIT BUY accepted "
            "(fill status not assumed)"
        ),
        "account": resolve_account(),
        "trade": trade,
        "order": order_result,
        "google_sheets": google_result,
    }


def paper_sell_spy():
    logger.info(
        "PAPER SELL START: account_id=%s environment=%s endpoint=%s",
        WEBULL_ACCOUNT_ID,
        WEBULL_ENVIRONMENT,
        WEBULL_ENDPOINT,
    )

    paper_trade = load_open_trade()

    if not paper_trade:
        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            result="FAILED",
            error="No logged open trade",
        )

        return {
            "success": False,
            "error": "No logged open trade",
        }

    # IMPORTANT: SELL never selects a new contract.
    contract_symbol = paper_trade.get("contract")

    logger.info(
        "PAPER SELL STORED CONTRACT: symbol=%s option_type=%s "
        "strike=%s expiration=%s",
        contract_symbol,
        paper_trade.get("option_type"),
        paper_trade.get("strike"),
        paper_trade.get("expiration"),
    )

    if not contract_symbol:
        return {
            "success": False,
            "error": "Open trade is missing contract symbol",
        }

    current_spy_price = extract_spy_price()

    if current_spy_price is None:
        return {
            "success": False,
            "error": "Unable to get current SPY price",
        }

    premium_result = get_option_price(contract_symbol)
    exit_premium = premium_result.get("premium")

    if exit_premium is None:
        return {
            "success": False,
            "error": "Unable to obtain current option premium",
        }

    entry_premium = paper_trade.get("entry_premium")

    if entry_premium in (None, 0):
        return {
            "success": False,
            "error": "Missing option entry premium",
        }

    profit_loss = round(
        (
            (exit_premium - entry_premium)
            / entry_premium
        ) * 100,
        2,
    )

    option_type = str(
        paper_trade.get("option_type", "CALL")
    ).strip().upper()

    strike = paper_trade.get("strike")
    expiration = paper_trade.get("expiration")

    logger.info(
        "PAPER SELL PREMIUM: contract=%s premium=%s",
        contract_symbol,
        exit_premium,
    )

    order_result = _webull_place_option_order(
        option_symbol=contract_symbol,
        option_type=option_type,
        side="SELL",
        quantity=1,
        limit_price=exit_premium,
        strike_price=strike,
        expiration=expiration,
        underlying_symbol="SPY",
    )

    if not order_result.get("success"):
        error = str(
            order_result.get("response")
            or order_result.get("error")
            or "Webull SELL failed"
        )

        logger.error(
            "PAPER SELL FAILED at Webull: contract=%s error=%s",
            contract_symbol,
            error,
        )

        journal_trade(
            event="WEBULL_SELL_FAILED",
            action="SELL",
            symbol="SPY",
            option_type=option_type,
            contract=contract_symbol,
            expiration=expiration,
            strike=strike,
            spy_price=current_spy_price,
            option_premium=exit_premium,
            entry_price=paper_trade.get("entry_price"),
            exit_price=current_spy_price,
            profit_loss=profit_loss,
            pricing_mode="OPTION_PREMIUM",
            result="FAILED",
            error=error,
        )

        return {
            "success": False,
            "message": "Webull Sandbox LIMIT SELL was NOT accepted",
            "contract": contract_symbol,
            "order": order_result,
        }

    actual_webull_status = (
        order_result.get("order_status")
        or "ACCEPTED"
    )

    # Only after Webull accepts the SELL do we close local/Google state.
    google_result = update_google_trade_closed(
        contract_symbol,
        current_spy_price,
        exit_premium,
        profit_loss,
        "OPTION_PREMIUM",
        "CLOSED",
        "",
    )

    local_trade_id = paper_trade.get("id")

    if local_trade_id is not None:
        try:
            close_trade(
                local_trade_id,
                current_spy_price,
                exit_premium,
                profit_loss,
                "OPTION_PREMIUM",
            )
        except Exception as e:
            logger.exception(
                "SQLite close failed after Webull SELL accepted: %s",
                e,
            )

    logger.info(
        "PAPER SELL ACCEPTED: contract=%s client_order_id=%s "
        "status=%s local_trade_closed=True",
        contract_symbol,
        order_result.get("client_order_id"),
        actual_webull_status,
    )

    return {
        "success": True,
        "message": (
            "Webull Sandbox LIMIT SELL accepted "
            "(fill status not assumed)"
        ),
        "account": resolve_account(),
        "trade": {
            "contract": contract_symbol,
            "option_type": option_type,
            "entry_price": paper_trade.get("entry_price"),
            "entry_premium": entry_premium,
            "exit_price": current_spy_price,
            "exit_premium": exit_premium,
            "profit_loss": profit_loss,
            "pricing_mode": "OPTION_PREMIUM",
            "result": "CLOSED",
            "order_status": actual_webull_status,
            "client_order_id": order_result.get("client_order_id"),
        },
        "order": order_result,
        "google_sheets": google_result,
    }


# ---------------------------------------------------------------------------
# Status / debug
# ---------------------------------------------------------------------------

def get_persistent_open_trade():
    return get_open_trade_from_google_sheets()


def test_google_sheets_connection():
    trade = get_open_trade_from_google_sheets()

    return {
        "success": True,
        "open_trade": trade,
    }


def paper_trade_status():
    trade = load_open_trade()

    return {
        "success": True,
        "open_trade": trade,
        "account": resolve_account(),
    }


def debug_option_chain():
    contracts = get_option_contracts("CALL")

    return {
        "success": not (
            isinstance(contracts, dict)
            and "error" in contracts
        ),
        "contracts": contracts,
    }


def debug_market_data():
    return get_spy_price()


def test_options():
    spy_price = extract_spy_price()

    if spy_price is None:
        return {
            "success": False,
            "error": "Unable to get SPY price for option test",
        }

    call = _select_contract_with_spy_price(
        "CALL",
        spy_price,
    )

    time.sleep(1.5)

    put = _select_contract_with_spy_price(
        "PUT",
        spy_price,
    )

    return {
        "success": (
            call.get("success", False)
            and put.get("success", False)
        ),
        "spy_price": spy_price,
        "call": call,
        "put": put,
    }
