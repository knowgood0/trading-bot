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


# ============================================================
# PAPER / SANDBOX ONLY
# ============================================================

WEBULL_ENDPOINT = "api.sandbox.webull.com"
WEBULL_ACCOUNT_ID = "DBGA758E2BRGBMISKLHF5JHCOA"
WEBULL_ACCOUNT_NUMBER = "DEA37KS6"
WEBULL_ACCOUNT_NAME = "Individual Margin"
WEBULL_ENVIRONMENT = "SANDBOX"

GOOGLE_SHEETS_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzYocjcr-9_YTeaplxao7WLF6aNWi41fDb8z3evhcBot2cy3h9QrU9Q7iePIveY9_mC"
    "/exec"
)

# Render Persistent Disk recommendation:
# Set TRADE_DB_PATH to a file on the mounted persistent disk, for example:
#   /var/data/paper_trades.db
# The default is only a development fallback and is NOT durable across a
# Render service replacement/redeploy unless the service filesystem is backed
# by a Persistent Disk.
TRADE_DB = os.environ.get("TRADE_DB_PATH", "paper_trades.db")

# Aggressive, marketable option LIMIT pricing.
BUY_BUFFER = float(os.environ.get("OPTION_BUY_BUFFER", "0.02"))
SELL_BUFFER = float(os.environ.get("OPTION_SELL_BUFFER", "0.02"))

logger = logging.getLogger(__name__)


# ============================================================
# Request serialization / caching
# ============================================================

_REQUEST_LOCK = threading.Lock()
_LAST_WEBULL_REQUEST = 0.0
_MIN_WEBULL_REQUEST_INTERVAL = 1.10

_SPY_CACHE = {"price": None, "time": 0.0}
_SPY_CACHE_SECONDS = 2.5


# ============================================================
# General helpers
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_client_order_id(prefix="TV"):
    return f"{prefix}{uuid.uuid4().hex.upper()}"[:32]


def resolve_account():
    return {
        "account_id": WEBULL_ACCOUNT_ID,
        "account_number": WEBULL_ACCOUNT_NUMBER,
        "account_name": WEBULL_ACCOUNT_NAME,
        "environment": WEBULL_ENVIRONMENT,
    }


def _throttle_webull():
    global _LAST_WEBULL_REQUEST

    with _REQUEST_LOCK:
        now = time.monotonic()
        wait = _MIN_WEBULL_REQUEST_INTERVAL - (now - _LAST_WEBULL_REQUEST)
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
        except Exception as exc:
            last_error = exc
            text = str(exc)
            if "TOO_MANY_REQUESTS" not in text and "429" not in text:
                raise
            time.sleep(2.0 * (attempt + 1))

    raise last_error


def _safe_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _first_dict_or_empty(data):
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict):
        return data
    return {}


# ============================================================
# SQLite persistence + safe schema migration
# ============================================================

SCHEMA_COLUMNS = {
    "open": "INTEGER NOT NULL DEFAULT 0",
    "state": "TEXT NOT NULL DEFAULT 'CLOSED'",
    "contract": "TEXT",
    "underlying_symbol": "TEXT DEFAULT 'SPY'",
    "option_type": "TEXT",
    "expiration": "TEXT",
    "strike": "REAL",
    "quantity": "INTEGER DEFAULT 1",
    "entry_price": "REAL",
    "entry_premium": "REAL",
    "entry_bid": "REAL",
    "entry_ask": "REAL",
    "entry_limit_price": "REAL",
    "entry_time": "TEXT",
    "entry_order_id": "TEXT",
    "entry_client_order_id": "TEXT",
    "entry_order_status": "TEXT",
    "position_intent": "TEXT",
    "exit_price": "REAL",
    "exit_premium": "REAL",
    "exit_bid": "REAL",
    "exit_ask": "REAL",
    "exit_limit_price": "REAL",
    "exit_time": "TEXT",
    "exit_order_id": "TEXT",
    "exit_client_order_id": "TEXT",
    "exit_order_status": "TEXT",
    "profit_loss": "REAL",
    "pricing_mode": "TEXT",
    "result": "TEXT",
    "error": "TEXT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}


def _connect_db():
    parent = os.path.dirname(os.path.abspath(TRADE_DB))
    os.makedirs(parent, exist_ok=True)
    connection = sqlite3.connect(TRADE_DB, timeout=20)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_database():
    connection = _connect_db()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                open INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'CLOSED',
                contract TEXT,
                underlying_symbol TEXT DEFAULT 'SPY',
                option_type TEXT,
                expiration TEXT,
                strike REAL,
                quantity INTEGER DEFAULT 1,
                entry_price REAL,
                entry_premium REAL,
                entry_bid REAL,
                entry_ask REAL,
                entry_limit_price REAL,
                entry_time TEXT,
                entry_order_id TEXT,
                entry_client_order_id TEXT,
                entry_order_status TEXT,
                position_intent TEXT,
                exit_price REAL,
                exit_premium REAL,
                exit_bid REAL,
                exit_ask REAL,
                exit_limit_price REAL,
                exit_time TEXT,
                exit_order_id TEXT,
                exit_client_order_id TEXT,
                exit_order_status TEXT,
                profit_loss REAL,
                pricing_mode TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        existing = {
            row[1] for row in connection.execute("PRAGMA table_info(paper_trades)")
        }

        for name, definition in SCHEMA_COLUMNS.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE paper_trades ADD COLUMN {name} {definition}"
                )

        # Safely normalize legacy rows without destroying their information.
        connection.execute(
            """
            UPDATE paper_trades
            SET state = CASE
                WHEN open = 1 THEN 'OPEN'
                ELSE COALESCE(NULLIF(result, ''), 'CLOSED')
            END
            WHERE state IS NULL OR state = '' OR state = 'CLOSED'
            """
        )
        connection.execute(
            """
            UPDATE paper_trades
            SET open = CASE WHEN state IN ('OPEN','PENDING_EXIT') THEN 1 ELSE 0 END
            WHERE state IS NOT NULL
            """
        )
        connection.commit()
    finally:
        connection.close()


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def load_latest_trade():
    _ensure_database()
    connection = _connect_db()
    try:
        row = connection.execute(
            "SELECT * FROM paper_trades ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def load_active_trade():
    _ensure_database()
    connection = _connect_db()
    try:
        row = connection.execute(
            """
            SELECT * FROM paper_trades
            WHERE state IN ('PENDING_ENTRY','OPEN','PENDING_EXIT')
            ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def load_open_trade():
    """Local working state only. Google Sheets is never authoritative."""
    trade = load_active_trade()
    if trade and trade.get("state") in ("OPEN", "PENDING_EXIT"):
        return trade
    return trade if trade and trade.get("state") == "PENDING_ENTRY" else None


def save_trade(trade):
    _ensure_database()
    now = utc_now()
    connection = _connect_db()
    try:
        columns = [
            "open", "state", "contract", "underlying_symbol", "option_type",
            "expiration", "strike", "quantity", "entry_price", "entry_premium",
            "entry_bid", "entry_ask", "entry_limit_price", "entry_time",
            "entry_order_id", "entry_client_order_id", "entry_order_status",
            "position_intent", "exit_price", "exit_premium", "exit_bid", "exit_ask",
            "exit_limit_price", "exit_time", "exit_order_id", "exit_client_order_id",
            "exit_order_status", "profit_loss", "pricing_mode", "result", "error",
            "created_at", "updated_at",
        ]
        values = [trade.get(c) for c in columns]
        if trade.get("created_at") is None:
            values[columns.index("created_at")] = now
        values[columns.index("updated_at")] = now

        placeholders = ",".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO paper_trades ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )
        trade["id"] = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.commit()
    finally:
        connection.close()
    return trade


def update_trade(trade_id, **fields):
    if not fields:
        return
    _ensure_database()
    fields["updated_at"] = utc_now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [trade_id]
    connection = _connect_db()
    try:
        connection.execute(
            f"UPDATE paper_trades SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()
    finally:
        connection.close()


def close_trade(trade_id, **fields):
    fields.update({"open": 0, "state": "CLOSED", "result": "CLOSED"})
    update_trade(trade_id, **fields)


def get_trade_history(limit=50):
    _ensure_database()
    connection = _connect_db()
    try:
        rows = connection.execute(
            "SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


# ============================================================
# Google Sheets journal — write/audit only
# ============================================================

def send_to_google_sheets(data):
    """Best-effort journal. Never controls trade state."""
    try:
        payload = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            GOOGLE_SHEETS_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TradingBot/8.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read().decode("utf-8")
        try:
            return json.loads(body)
        except Exception:
            return {"success": True, "response": body}
    except Exception as exc:
        logger.warning("Google Sheets journal failed (non-blocking): %s", exc)
        return {"success": False, "error": str(exc), "non_blocking": True}


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
    bid=None,
    ask=None,
    limit_price=None,
    price_buffer=None,
    client_order_id=None,
    order_id=None,
    order_status=None,
    state=None,
):
    return send_to_google_sheets({
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
        "state": state,
        "error": error,
        "bid": bid,
        "ask": ask,
        "limit_price": limit_price,
        "price_buffer": price_buffer,
        "client_order_id": client_order_id,
        "order_id": order_id,
        "order_status": order_status,
    })


def update_google_trade_closed(*args, **kwargs):
    """Compatibility wrapper; this only journals an audit event."""
    data = {
        "action": "close_trade",
        "timestamp": utc_now(),
    }
    if args:
        keys = ["contract", "exit_price", "exit_premium", "profit_loss", "pricing_mode", "result", "error"]
        data.update({k: v for k, v in zip(keys, args)})
    data.update(kwargs)
    return send_to_google_sheets(data)


def get_persistent_open_trade():
    # Compatibility name retained, but intentionally local DB only.
    return load_open_trade()


def test_google_sheets_connection():
    result = send_to_google_sheets({
        "event": "GOOGLE_TEST",
        "timestamp": utc_now(),
        "source_of_truth": "WEBULL_PAPER_ACCOUNT",
    })
    return result


# ============================================================
# Webull clients / account
# ============================================================

def get_clients():
    app_key = os.environ.get("WEBULL_APP_KEY")
    app_secret = os.environ.get("WEBULL_APP_SECRET")
    if not app_key:
        raise RuntimeError("WEBULL_APP_KEY environment variable is missing")
    if not app_secret:
        raise RuntimeError("WEBULL_APP_SECRET environment variable is missing")

    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", WEBULL_ENDPOINT)
    return TradeClient(api_client), DataClient(api_client)


def test_webull_connection():
    try:
        trade_client, _ = get_clients()
        response = _webull_call(trade_client.account_v2.get_account_list)
        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "account": response.json(),
            "configured_account": resolve_account(),
            "environment": WEBULL_ENVIRONMENT,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
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
            response = _webull_call(trade_client.account_v2.get_account_balance, account_id)
            result["balance_status"] = response.status_code
            result["balance"] = response.json()
        except Exception as exc:
            result["errors"].append("BALANCE: " + str(exc))
        try:
            response = _webull_call(trade_client.account_v2.get_account_position, account_id)
            result["positions_status"] = response.status_code
            result["positions"] = response.json()
        except Exception as exc:
            result["errors"].append("POSITIONS: " + str(exc))
    except Exception as exc:
        result["errors"].append("CLIENT: " + str(exc))

    result["success"] = result["balance_status"] == 200 and result["positions_status"] == 200
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
            response = _webull_call(trade_client.account_v2.get_account_list)
            diagnostic["account_list_status"] = response.status_code
            diagnostic["account_list"] = response.json()
        except Exception as exc:
            diagnostic["error"] = "ACCOUNT LIST: " + str(exc)

        configured = _query_account(WEBULL_ACCOUNT_ID, WEBULL_ACCOUNT_NAME)
        diagnostic["accounts"]["configured"] = configured
        diagnostic["success"] = configured.get("success", False)
    except Exception as exc:
        diagnostic["error"] = str(exc)
    return diagnostic


def account_order_capability_test():
    diag = account_diagnostic()
    configured = resolve_account()
    account_list = diag.get("account_list")
    account_ids = []

    if isinstance(account_list, list):
        items = account_list
    elif isinstance(account_list, dict):
        items = []
        for key in ("account", "accounts", "data", "items"):
            if isinstance(account_list.get(key), list):
                items = account_list[key]
                break
    else:
        items = []

    for item in items:
        if isinstance(item, dict) and item.get("account_id"):
            account_ids.append(item["account_id"])

    present = configured["account_id"] in account_ids if account_ids else None
    notes = [
        "This endpoint is READ-ONLY. No order was submitted.",
        "Successful account lookup (HTTP 200) does NOT prove order permissions.",
    ]
    if present is True:
        notes.append("Configured account_id appears in the account list returned by Webull.")
    elif present is False:
        notes.append("WARNING: configured account_id is NOT present in the account list returned by Webull.")

    return {
        "success": True,
        "endpoint": "/order-capability-test",
        "read_only": True,
        "order_submitted": False,
        "environment": WEBULL_ENVIRONMENT,
        "webull_endpoint": WEBULL_ENDPOINT,
        "configured_account": configured,
        "account_diagnostic": diag,
        "account_ids_from_list": account_ids,
        "configured_id_present_in_list": present,
        "notes": notes,
        "message": "Diagnostic only. No order was placed.",
    }


def inspect_order_api():
    """Read-only inspection; never submits an order."""
    info = {
        "success": True,
        "read_only": True,
        "order_submitted": False,
        "environment": WEBULL_ENVIRONMENT,
        "webull_endpoint": WEBULL_ENDPOINT,
        "configured_account": resolve_account(),
        "trade_client_attrs": [],
        "order_v3_attrs": [],
        "account_v2_attrs": [],
        "error": None,
        "notes": ["This endpoint is READ-ONLY. No order was submitted."],
    }
    try:
        trade_client, _ = get_clients()
        info["trade_client_attrs"] = sorted(a for a in dir(trade_client) if not a.startswith("_"))
        if hasattr(trade_client, "order_v3"):
            info["order_v3_attrs"] = sorted(a for a in dir(trade_client.order_v3) if not a.startswith("_"))
        if hasattr(trade_client, "account_v2"):
            info["account_v2_attrs"] = sorted(a for a in dir(trade_client.account_v2) if not a.startswith("_"))
    except Exception as exc:
        info["success"] = False
        info["error"] = str(exc)
    return info


# ============================================================
# Webull positions — authoritative external state
# ============================================================

def _position_items(positions_response):
    if isinstance(positions_response, list):
        return positions_response
    if isinstance(positions_response, dict):
        for key in ("positions", "data", "items"):
            if isinstance(positions_response.get(key), list):
                return positions_response[key]
    return []


def get_webull_positions():
    try:
        trade_client, _ = get_clients()
        response = _webull_call(
            trade_client.account_v2.get_account_position,
            WEBULL_ACCOUNT_ID,
        )
        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "account": resolve_account(),
            "positions": response.json(),
        }
    except Exception as exc:
        return {
            "success": False,
            "account": resolve_account(),
            "error": str(exc),
        }


def _option_position_matches(position, option_symbol=None, option_type=None, strike=None, expiration=None):
    if not isinstance(position, dict):
        return False
    if str(position.get("instrument_type") or "").upper() != "OPTION":
        return False

    legs = position.get("legs") or []
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        leg_type = str(leg.get("option_type") or "").upper()
        leg_strike = _safe_float(leg.get("option_exercise_price"))
        leg_exp = str(leg.get("option_expire_date") or "")[:10]
        leg_symbol = str(leg.get("symbol") or "")

        if option_type and leg_type != str(option_type).upper():
            continue
        if strike is not None and (leg_strike is None or abs(leg_strike - float(strike)) > 0.0001):
            continue
        if expiration and leg_exp != str(expiration)[:10]:
            continue
        if option_symbol and leg_symbol == option_symbol:
            return True
        if option_symbol and leg_symbol != option_symbol:
            # Webull's position response uses the underlying symbol in the leg.
            # Contract identity is therefore matched by option_type/strike/expiry.
            if option_type or strike is not None or expiration:
                return True
            continue
        if not option_symbol:
            return True
    return False


def _parse_occ_option_symbol(option_symbol):
    text = str(option_symbol or "").strip().upper()
    if not text.startswith("SPY") or len(text) < 21:
        return None
    try:
        # Standard SPY OCC form: SPY + YYMMDD + C/P + 8-digit strike*1000.
        exp = datetime.strptime(text[3:9], "%y%m%d").strftime("%Y-%m-%d")
        cp = text[9]
        if cp not in ("C", "P"):
            return None
        strike = int(text[10:18]) / 1000.0
        return {"option_type": "CALL" if cp == "C" else "PUT", "strike": strike, "expiration": exp}
    except Exception:
        return None


def get_webull_option_position(option_symbol=None, option_type=None, strike=None, expiration=None):
    parsed = _parse_occ_option_symbol(option_symbol) if option_symbol else None
    if parsed:
        option_type = option_type or parsed["option_type"]
        strike = strike if strike is not None else parsed["strike"]
        expiration = expiration or parsed["expiration"]

    result = get_webull_positions()
    if not result.get("success"):
        return result

    positions = _position_items(result.get("positions"))
    matches = [
        p for p in positions
        if _option_position_matches(p, option_symbol, option_type, strike, expiration)
        and (_safe_float(p.get("quantity")) or 0) > 0
    ]

    return {
        "success": True,
        "found": bool(matches),
        "symbol": option_symbol,
        "option_type": option_type,
        "strike": strike,
        "expiration": expiration,
        "positions": matches,
    }




def _build_occ_option_symbol(underlying_symbol, expiration, option_type, strike):
    """Build a standard OCC symbol for the SPY contract returned by Webull."""
    root = str(underlying_symbol or "SPY").strip().upper()
    exp = str(expiration or "")[:10]
    if len(exp) != 10 or strike is None or str(option_type).upper() not in ("CALL", "PUT"):
        return None
    try:
        dt = datetime.strptime(exp, "%Y-%m-%d")
        yy = dt.strftime("%y")
        mm = dt.strftime("%m")
        dd = dt.strftime("%d")
        strike_int = int(round(float(strike) * 1000))
        cp = "C" if str(option_type).upper() == "CALL" else "P"
        return f"{root}{yy}{mm}{dd}{cp}{strike_int:08d}"
    except Exception:
        return None


def _recover_trade_from_single_webull_position(position):
    details = _position_contract_details(position)
    contract = _build_occ_option_symbol(
        details.get("underlying_symbol"),
        details.get("expiration"),
        details.get("option_type"),
        details.get("strike"),
    )
    if not contract or details.get("option_type") not in ("CALL", "PUT") or not details.get("strike") or not details.get("expiration"):
        return None
    return {
        "open": 1,
        "state": "OPEN",
        "contract": contract,
        "underlying_symbol": details.get("underlying_symbol") or "SPY",
        "option_type": details.get("option_type"),
        "expiration": details.get("expiration"),
        "strike": details.get("strike"),
        "quantity": details.get("quantity") or 1,
        "entry_price": None,
        "entry_premium": details.get("entry_premium"),
        "entry_bid": None,
        "entry_ask": None,
        "entry_limit_price": None,
        "entry_time": None,
        "entry_order_id": None,
        "entry_client_order_id": None,
        "entry_order_status": "FILLED_BY_POSITION",
        "position_intent": "BUY_TO_OPEN",
        "pricing_mode": "RECOVERED_FROM_WEBULL_POSITION",
        "result": "OPEN",
        "error": "Recovered from authoritative Webull PAPER position; original local record was unavailable.",
    }

def _find_single_long_option_position(positions_response):
    options = []
    for position in _position_items(positions_response):
        if not isinstance(position, dict):
            continue
        if str(position.get("instrument_type") or "").upper() != "OPTION":
            continue
        qty = _safe_float(position.get("quantity"))
        if qty is not None and qty > 0:
            options.append(position)
    if len(options) == 1:
        return options[0]
    return None


def _position_contract_details(position):
    legs = position.get("legs") or [] if isinstance(position, dict) else []
    leg = legs[0] if legs and isinstance(legs[0], dict) else {}
    option_type = str(leg.get("option_type") or "").upper()
    strike = _safe_float(leg.get("option_exercise_price"))
    expiration = str(leg.get("option_expire_date") or "")[:10]
    quantity = int(_safe_float(position.get("quantity")) or 0)
    return {
        "option_type": option_type,
        "strike": strike,
        "expiration": expiration,
        "quantity": quantity,
        "underlying_symbol": str(position.get("symbol") or "SPY"),
        "entry_premium": _safe_float(position.get("cost_price")),
        "position_id": position.get("position_id"),
        "leg_id": leg.get("leg_id"),
    }


# ============================================================
# Market data / option contracts
# ============================================================

def get_spy_price():
    now = time.monotonic()
    if _SPY_CACHE["price"] is not None and now - _SPY_CACHE["time"] < _SPY_CACHE_SECONDS:
        return {"success": True, "data": {"price": _SPY_CACHE["price"], "cached": True}}
    try:
        _, data_client = get_clients()
        response = _webull_call(
            data_client.market_data.get_snapshot,
            "SPY",
            Category.US_STOCK.name,
        )
        data = response.json()
        item = _first_dict_or_empty(data)
        if item.get("price") is not None:
            _SPY_CACHE["price"] = float(item["price"])
            _SPY_CACHE["time"] = time.monotonic()
        return {"success": 200 <= response.status_code < 300, "data": data}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def extract_spy_price():
    result = get_spy_price()
    if not result.get("success"):
        return None
    data = result.get("data")
    item = _first_dict_or_empty(data)
    return _safe_float(item.get("price"))


def get_option_contracts(option_type="CALL"):
    try:
        _, data_client = get_clients()
        normalized_type = str(option_type).upper()
        if normalized_type not in ("CALL", "PUT"):
            return {"error": "Invalid option type: " + normalized_type}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    except Exception as exc:
        return {"error": str(exc)}


def _select_contract_with_spy_price(option_type, spy_price):
    try:
        normalized_type = str(option_type).upper()
        if normalized_type not in ("CALL", "PUT"):
            return {"success": False, "error": "Option type must be CALL or PUT"}
        if spy_price is None:
            return {"success": False, "error": "SPY price is required"}

        contracts = get_option_contracts(normalized_type)
        if isinstance(contracts, dict) and "error" in contracts:
            return {"success": False, "error": contracts["error"]}
        if not isinstance(contracts, list):
            return {"success": False, "error": "Unexpected option contract response"}

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        valid = []
        for contract in contracts:
            try:
                expiration = str(contract.get("expiration_date") or contract.get("expiration") or "")[:10]
                strike_value = contract.get("strike_price")
                if strike_value is None:
                    continue
                strike = float(strike_value)
                contract_type = str(contract.get("option_type") or "").upper()
                def_type = str(contract.get("def_type") or "").upper()
                style = str(contract.get("style") or "").upper()
                tradable_status = str(contract.get("tradable_status") or "").upper()
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

        if not valid:
            return {"success": False, "error": f"No valid 0DTE {normalized_type} contracts found for today"}

        valid.sort(key=lambda x: abs(float(x["strike_price"]) - float(spy_price)))
        selected = valid[0]
        return {
            "success": True,
            "spy_price": float(spy_price),
            "selected_contract": {
                "symbol": selected.get("symbol"),
                "underlying_symbol": selected.get("underlying_symbol", "SPY"),
                "type": normalized_type,
                "strike": selected.get("strike_price"),
                "expiration": selected.get("expiration_date") or selected.get("expiration"),
                "instrument_id": selected.get("instrument_id"),
                "underlying_instrument_id": selected.get("underlying_instrument_id"),
                "raw": selected,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def select_0dte_atm_contract(option_type="CALL"):
    spy_price = extract_spy_price()
    if spy_price is None:
        return {"success": False, "error": "Unable to get current SPY price"}
    return _select_contract_with_spy_price(option_type, spy_price)


def select_contract(option_type="CALL"):
    return select_0dte_atm_contract(option_type)


def get_option_price(option_symbol):
    """Return premium plus bid/ask for aggressive LIMIT pricing."""
    try:
        _, data_client = get_clients()
        response = _webull_call(
            data_client.option_market_data.get_option_snapshot,
            option_symbol,
            Category.US_OPTION.name,
        )
        data = response.json()
        item = _first_dict_or_empty(data)
        premium = None
        for field in ("price", "latest_price", "last_price", "last", "close", "mark_price"):
            if item.get(field) is not None:
                premium = float(item[field])
                break
        return {
            "success": 200 <= response.status_code < 300,
            "premium": premium,
            "bid": _safe_float(item.get("bid")),
            "ask": _safe_float(item.get("ask")),
            "data": data,
        }
    except Exception as exc:
        return {"success": False, "premium": None, "bid": None, "ask": None, "error": str(exc)}


def _aggressive_buy_price(price_result):
    ask = price_result.get("ask")
    premium = price_result.get("premium")
    if ask is not None and ask > 0:
        return round(ask + BUY_BUFFER, 2), "AGGRESSIVE_ASK_LIMIT"
    if premium is not None:
        return round(premium, 2), "PRICE_FALLBACK"
    return None, None


def _aggressive_sell_price(price_result):
    bid = price_result.get("bid")
    premium = price_result.get("premium")
    if bid is not None and bid > 0:
        candidate = round(bid - SELL_BUFFER, 2)
        if candidate > 0.01:
            return candidate, "AGGRESSIVE_BID_LIMIT"
        if premium is not None:
            return round(premium, 2), "PRICE_FALLBACK"
        return round(bid, 2), "AGGRESSIVE_BID_LIMIT"
    if premium is not None:
        return round(premium, 2), "PRICE_FALLBACK"
    return None, None


# ============================================================
# Webull order submission
# ============================================================
# Evidence supplied in Bot_scratchpad.txt establishes that the installed
# SDK exposes order_v3.place_order, and the prior successful test established
# this as the working US/Sandbox order path. The option leg uses the underlying
# symbol (SPY), while strike/expiration/option_type identify the option.
# We preserve that exact working structure rather than guessing a new schema.


def _webull_place_option_order(
    option_symbol,
    option_type,
    side,
    quantity,
    limit_price,
    position_intent,
    strike_price,
    expiration,
    underlying_symbol="SPY",
):
    try:
        trade_client, _ = get_clients()
        normalized_type = str(option_type).upper()
        normalized_side = str(side).upper()
        normalized_intent = str(position_intent).upper()
        under = str(underlying_symbol or "SPY").upper()

        if normalized_type not in ("CALL", "PUT"):
            return {"success": False, "error": "Invalid option type"}
        if normalized_side not in ("BUY", "SELL"):
            return {"success": False, "error": "Invalid option side"}
        if normalized_intent not in ("BUY_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_OPEN", "SELL_TO_CLOSE"):
            return {"success": False, "error": "Invalid position intent"}
        if limit_price is None:
            return {"success": False, "error": "Missing option limit price"}
        if strike_price is None or expiration is None:
            return {"success": False, "error": "Missing option strike or expiration"}

        client_order_id = make_client_order_id("TV")
        order = {
            "client_order_id": client_order_id,
            "combo_type": "NORMAL",
            "option_strategy": "SINGLE",
            "instrument_type": "OPTION",
            "entrust_type": "QTY",
            "symbol": under,
            "market": "US",
            "side": normalized_side,
            "order_type": "LIMIT",
            "limit_price": f"{float(limit_price):.2f}",
            "quantity": str(int(quantity)),
            "time_in_force": "DAY",
            "position_intent": normalized_intent,
            "legs": [
                {
                    "side": normalized_side,
                    "quantity": str(int(quantity)),
                    "symbol": under,
                    "strike_price": f"{float(strike_price):.2f}",
                    "option_expire_date": str(expiration)[:10],
                    "instrument_type": "OPTION",
                    "option_type": normalized_type,
                    "market": "US",
                }
            ],
        }

        response = _webull_call(
            trade_client.order_v3.place_order,
            WEBULL_ACCOUNT_ID,
            [order],
        )
        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw": str(response)}

        accepted = 200 <= response.status_code < 300
        return {
            "success": accepted,
            "accepted": accepted,
            "status_code": response.status_code,
            "client_order_id": client_order_id,
            "account": resolve_account(),
            "response": response_data,
            "prepared_order": order,
            "option_contract_symbol": option_symbol,
            "order_status": _extract_order_status(response_data),
            "order_status_note": (
                "Accepted/submitted; this does not mean filled."
                if accepted else "Webull did not accept the order request."
            ),
        }
    except Exception as exc:
        return {
            "success": False,
            "accepted": False,
            "account": resolve_account(),
            "error": str(exc),
        }


def _extract_order_status(data):
    if not isinstance(data, dict):
        return None
    for key in ("status", "order_status", "orderStatus", "state"):
        value = data.get(key)
        if value not in (None, ""):
            return value
    for key in ("order", "data", "result"):
        nested = data.get(key)
        if isinstance(nested, dict):
            found = _extract_order_status(nested)
            if found is not None:
                return found
        elif isinstance(nested, list):
            for item in nested:
                found = _extract_order_status(item)
                if found is not None:
                    return found
    return None


def _order_status_class(status):
    if status is None:
        return "UNKNOWN"
    text = str(status).upper().replace(" ", "_")
    if "PARTIAL" in text and "FILL" in text:
        return "PARTIAL"
    if "FILL" in text or text in ("COMPLETED", "COMPLETE"):
        return "FILLED"
    if any(x in text for x in ("REJECT", "INVALID")):
        return "REJECTED"
    if any(x in text for x in ("CANCEL", "CANCELED", "CANCELLED")):
        return "CANCELED"
    if any(x in text for x in ("WORKING", "NEW", "OPEN", "PENDING", "SUBMIT")):
        return "PENDING"
    return "UNKNOWN"


def test_order_detail(client_order_id):
    try:
        trade_client, _ = get_clients()
        response = _webull_call(
            trade_client.order_v3.get_order_detail,
            WEBULL_ACCOUNT_ID,
            client_order_id,
        )
        data = response.json()
        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "account": resolve_account(),
            "client_order_id": client_order_id,
            "order": data,
            "order_status": _extract_order_status(data),
            "order_status_class": _order_status_class(_extract_order_status(data)),
        }
    except Exception as exc:
        return {"success": False, "account": resolve_account(), "error": str(exc)}


# ============================================================
# Reconciliation
# ============================================================

def _reconcile_active_trade(trade=None):
    trade = trade or load_active_trade()
    if not trade:
        return {"success": True, "trade": None, "changed": False}

    positions_result = get_webull_positions()
    if not positions_result.get("success"):
        return {
            "success": False,
            "trade": trade,
            "changed": False,
            "error": "Unable to verify Webull PAPER positions",
            "webull": positions_result,
        }

    positions = positions_result.get("positions")
    matching = get_webull_option_position(
        trade.get("contract"),
        trade.get("option_type"),
        trade.get("strike"),
        trade.get("expiration"),
    )
    if not matching.get("success"):
        return {"success": False, "trade": trade, "changed": False, "error": "Position verification failed"}

    found = matching.get("found", False)
    state = trade.get("state")
    changed = False

    client_order_id = trade.get("entry_client_order_id") if state == "PENDING_ENTRY" else trade.get("exit_client_order_id")
    order_detail = test_order_detail(client_order_id) if client_order_id else None
    order_class = _order_status_class(order_detail.get("order_status")) if order_detail and order_detail.get("success") else "UNKNOWN"

    if state == "PENDING_ENTRY":
        if found:
            update_trade(
                trade["id"],
                open=1,
                state="OPEN",
                result="OPEN",
                entry_order_status=order_detail.get("order_status") if order_detail else trade.get("entry_order_status"),
            )
            changed = True
        elif order_class in ("REJECTED", "CANCELED"):
            update_trade(
                trade["id"],
                open=0,
                state=order_class,
                result=order_class,
                error=f"Entry order status: {order_detail.get('order_status')}",
                entry_order_status=order_detail.get("order_status"),
            )
            changed = True

    elif state == "OPEN":
        # Do not automatically close local state merely because a transient
        # lookup is empty; this branch is reached only after a successful
        # position query. If the actual position is gone, the local record is
        # stale and is reconciled as closed.
        if not found:
            update_trade(
                trade["id"],
                open=0,
                state="CLOSED",
                result="CLOSED",
                exit_time=utc_now(),
                error="Webull PAPER position no longer present during reconciliation",
            )
            changed = True

    elif state == "PENDING_EXIT":
        if found:
            if order_class in ("REJECTED", "CANCELED"):
                update_trade(
                    trade["id"],
                    open=1,
                    state="OPEN",
                    result="OPEN",
                    exit_order_status=order_detail.get("order_status") if order_detail else trade.get("exit_order_status"),
                    error=f"Exit order status: {order_detail.get('order_status')}",
                )
                changed = True
        else:
            # We had verified the position before submitting the SELL. If a
            # later successful position query shows it gone, the position is
            # actually closed. We still record the actual order status when
            # available; we never call an accepted order a fill by itself.
            update_trade(
                trade["id"],
                open=0,
                state="CLOSED",
                result="CLOSED",
                exit_time=utc_now(),
                exit_order_status=order_detail.get("order_status") if order_detail else trade.get("exit_order_status"),
            )
            changed = True

    refreshed = load_active_trade() or load_latest_trade()
    return {"success": True, "trade": refreshed, "changed": changed, "webull": positions_result, "order_detail": order_detail}


def reconcile_paper_state():
    return _reconcile_active_trade()


# ============================================================
# Paper trading
# ============================================================

def paper_buy_spy(option_type="CALL"):
    normalized_type = str(option_type).upper()
    if normalized_type not in ("CALL", "PUT"):
        return {"success": False, "error": "Option type must be CALL or PUT", "http_status": 400}

    reconcile = _reconcile_active_trade()
    if not reconcile.get("success"):
        return {
            "success": False,
            "error": "Unable to verify current Webull PAPER position state. BUY blocked for safety.",
            "reconciliation": reconcile,
            "http_status": 503,
        }

    existing_trade = load_active_trade()
    if existing_trade and existing_trade.get("state") in ("PENDING_ENTRY", "OPEN", "PENDING_EXIT"):
        return {
            "success": False,
            "error": f"An active bot trade is already in state {existing_trade.get('state')}.",
            "trade": existing_trade,
            "http_status": 409,
        }

    positions_result = get_webull_positions()
    if not positions_result.get("success"):
        return {
            "success": False,
            "error": "Unable to verify Webull PAPER positions. BUY blocked for safety.",
            "webull": positions_result,
            "http_status": 503,
        }

    existing_position = _find_single_long_option_position(positions_result.get("positions"))
    if existing_position:
        return {
            "success": False,
            "error": "Webull PAPER already has an open option position. BUY blocked to prevent stacking.",
            "position": existing_position,
            "http_status": 409,
        }

    spy_price = extract_spy_price()
    if spy_price is None:
        error = "Unable to get current SPY price"
        journal_trade(event="BUY_FAILED", action="BUY", symbol="SPY", option_type=normalized_type, result="FAILED", error=error)
        return {"success": False, "error": error, "http_status": 503}

    contract_result = _select_contract_with_spy_price(normalized_type, spy_price)
    if not contract_result.get("success"):
        error = contract_result.get("error", "Contract selection failed")
        journal_trade(event="BUY_FAILED", action="BUY", symbol="SPY", option_type=normalized_type, spy_price=spy_price, result="FAILED", error=error)
        return {**contract_result, "http_status": 503}

    selected = contract_result["selected_contract"]
    contract_symbol = selected.get("symbol")
    underlying_symbol = selected.get("underlying_symbol", "SPY")
    expiration = selected.get("expiration")
    strike = selected.get("strike")
    if not contract_symbol or strike is None or expiration is None:
        return {"success": False, "error": "Selected option is missing symbol, strike, or expiration", "http_status": 500}

    pr = get_option_price(contract_symbol)
    premium = pr.get("premium")
    if premium is None:
        error = "Unable to obtain option premium. No Webull order submitted."
        journal_trade(event="BUY_FAILED", action="BUY", symbol="SPY", option_type=normalized_type, contract=contract_symbol, expiration=expiration, strike=strike, spy_price=spy_price, result="FAILED", error=error)
        return {"success": False, "error": error, "contract": contract_symbol, "premium": pr, "http_status": 503}

    buy_limit, buy_mode = _aggressive_buy_price(pr)
    if buy_limit is None:
        return {"success": False, "error": "Unable to calculate a valid BUY limit price", "premium": pr, "http_status": 503}

    order_result = _webull_place_option_order(
        option_symbol=contract_symbol,
        option_type=normalized_type,
        side="BUY",
        quantity=1,
        limit_price=buy_limit,
        position_intent="BUY_TO_OPEN",
        strike_price=strike,
        expiration=expiration,
        underlying_symbol=underlying_symbol,
    )

    if not order_result.get("success"):
        error = str(order_result.get("response") or order_result.get("error") or "Webull BUY failed")
        journal_trade(event="WEBULL_BUY_FAILED", action="BUY", symbol="SPY", option_type=normalized_type, contract=contract_symbol, expiration=expiration, strike=strike, spy_price=spy_price, option_premium=premium, result="FAILED", error=error, bid=pr.get("bid"), ask=pr.get("ask"), limit_price=buy_limit, price_buffer=BUY_BUFFER, pricing_mode=buy_mode, client_order_id=order_result.get("client_order_id"))
        return {"success": False, "message": "Webull Sandbox LIMIT BUY was NOT accepted", "contract": contract_symbol, "premium": premium, "limit_price_submitted": buy_limit, "pricing_mode": buy_mode, "bid": pr.get("bid"), "ask": pr.get("ask"), "order": order_result, "http_status": 502}

    client_order_id = order_result.get("client_order_id")
    trade = {
        "open": 0,
        "state": "PENDING_ENTRY",
        "contract": contract_symbol,
        "underlying_symbol": underlying_symbol,
        "option_type": normalized_type,
        "expiration": expiration,
        "strike": float(strike),
        "quantity": 1,
        "entry_price": spy_price,
        "entry_premium": premium,
        "entry_bid": pr.get("bid"),
        "entry_ask": pr.get("ask"),
        "entry_limit_price": buy_limit,
        "entry_time": utc_now(),
        "entry_order_id": order_result.get("response", {}).get("order_id") if isinstance(order_result.get("response"), dict) else None,
        "entry_client_order_id": client_order_id,
        "entry_order_status": order_result.get("order_status") or "ACCEPTED",
        "position_intent": "BUY_TO_OPEN",
        "pricing_mode": buy_mode,
        "result": "PENDING_ENTRY",
        "error": None,
    }
    trade = save_trade(trade)

    journal_result = journal_trade(
        event="WEBULL_BUY_ACCEPTED",
        action="BUY",
        symbol="SPY",
        option_type=normalized_type,
        contract=contract_symbol,
        expiration=expiration,
        strike=strike,
        spy_price=spy_price,
        option_premium=premium,
        entry_price=spy_price,
        pricing_mode=buy_mode,
        result="PENDING_ENTRY",
        state="PENDING_ENTRY",
        bid=pr.get("bid"),
        ask=pr.get("ask"),
        limit_price=buy_limit,
        price_buffer=BUY_BUFFER,
        client_order_id=client_order_id,
        order_id=trade.get("entry_order_id"),
        order_status=trade.get("entry_order_status"),
    )

    # Reconcile immediately once. If the order filled fast, this promotes the
    # state to OPEN; otherwise it remains PENDING_ENTRY.
    reconcile_after = _reconcile_active_trade(trade)
    final_trade = reconcile_after.get("trade") or trade

    return {
        "success": True,
        "message": "Webull Sandbox LIMIT BUY accepted/submitted; fill status is not assumed.",
        "account": resolve_account(),
        "trade": final_trade,
        "order": order_result,
        "google_sheets": journal_result,
        "http_status": 200,
    }


def paper_sell_spy():
    reconcile = _reconcile_active_trade()
    if not reconcile.get("success"):
        return {
            "success": False,
            "error": "Unable to verify Webull PAPER position state. SELL blocked for safety.",
            "reconciliation": reconcile,
            "http_status": 503,
        }

    paper_trade = load_active_trade()
    if not paper_trade:
        # Recovery path for a Render restart/redeploy where the local DB was
        # lost or was not mounted, but Webull still has the authoritative
        # position. Only recover automatically when exactly one long option
        # position exists, so we never guess which position to close.
        positions_result = get_webull_positions()
        if not positions_result.get("success"):
            return {"success": False, "error": "No local trade and Webull position lookup failed. Blind SELL prohibited.", "http_status": 503}
        position = _find_single_long_option_position(positions_result.get("positions"))
        if position is None:
            journal_trade(event="SELL_FAILED", action="SELL", symbol="SPY", result="FAILED", error="No active local trade and no uniquely recoverable Webull option position")
            return {"success": False, "error": "No active local trade and no uniquely recoverable Webull option position", "http_status": 409}
        recovered = _recover_trade_from_single_webull_position(position)
        if recovered is None:
            return {"success": False, "error": "Webull position exists but its option identity could not be safely reconstructed. SELL blocked.", "position": position, "http_status": 409}
        paper_trade = save_trade(recovered)
        journal_trade(event="WEBULL_POSITION_RECOVERED", action="RECOVERY", symbol="SPY", option_type=paper_trade.get("option_type"), contract=paper_trade.get("contract"), expiration=paper_trade.get("expiration"), strike=paper_trade.get("strike"), option_premium=paper_trade.get("entry_premium"), result="OPEN", state="OPEN", error=paper_trade.get("error"))

    if paper_trade.get("state") == "PENDING_ENTRY":
        return {"success": False, "error": "Entry order has not yet been verified as filled. SELL blocked until a Webull position exists.", "trade": paper_trade, "http_status": 409}

    if paper_trade.get("state") == "PENDING_EXIT":
        return {"success": True, "message": "An exit order is already pending; duplicate SELL blocked.", "trade": paper_trade, "http_status": 200}

    if paper_trade.get("state") != "OPEN":
        return {"success": False, "error": f"Trade is not OPEN; current state is {paper_trade.get('state')}", "trade": paper_trade, "http_status": 409}

    contract_symbol = paper_trade.get("contract")
    option_type = str(paper_trade.get("option_type") or "").upper()
    strike = paper_trade.get("strike")
    expiration = paper_trade.get("expiration")
    quantity = int(paper_trade.get("quantity") or 1)

    if not contract_symbol or option_type not in ("CALL", "PUT") or strike is None or not expiration:
        return {"success": False, "error": "Local trade is missing required option identity", "http_status": 500}

    # REQUIRED SAFETY CHECK: actual Webull position must exist immediately
    # before a SELL is submitted.
    position_check = get_webull_option_position(contract_symbol, option_type, strike, expiration)
    if not position_check.get("success"):
        return {"success": False, "error": "Webull PAPER position lookup failed. Blind SELL prohibited.", "webull": position_check, "http_status": 503}
    if not position_check.get("found"):
        return {"success": False, "error": "No matching Webull PAPER position exists. SELL not submitted.", "webull": position_check, "http_status": 409}

    current_spy_price = extract_spy_price()
    if current_spy_price is None:
        return {"success": False, "error": "Unable to get current SPY price", "http_status": 503}

    pr = get_option_price(contract_symbol)
    exit_premium = pr.get("premium")
    if exit_premium is None:
        return {"success": False, "error": "Unable to obtain current option premium", "http_status": 503}

    entry_premium = paper_trade.get("entry_premium")
    if entry_premium in (None, 0):
        # Fall back to the actual Webull position cost if available.
        matches = position_check.get("positions") or []
        if matches:
            entry_premium = _position_contract_details(matches[0]).get("entry_premium")
    if entry_premium in (None, 0):
        return {"success": False, "error": "Missing option entry premium", "http_status": 500}

    profit_loss = round(((exit_premium - entry_premium) / entry_premium) * 100, 2)
    sell_limit, sell_mode = _aggressive_sell_price(pr)
    if sell_limit is None:
        return {"success": False, "error": "Unable to calculate a valid SELL limit price", "premium": pr, "http_status": 503}

    order_result = _webull_place_option_order(
        option_symbol=contract_symbol,
        option_type=option_type,
        side="SELL",
        quantity=quantity,
        limit_price=sell_limit,
        position_intent="SELL_TO_CLOSE",
        strike_price=strike,
        expiration=expiration,
        underlying_symbol="SPY",
    )

    if not order_result.get("success"):
        error = str(order_result.get("response") or order_result.get("error") or "Webull SELL failed")
        journal_trade(event="WEBULL_SELL_FAILED", action="SELL", symbol="SPY", option_type=option_type, contract=contract_symbol, expiration=expiration, strike=strike, spy_price=current_spy_price, option_premium=exit_premium, entry_price=paper_trade.get("entry_price"), exit_price=current_spy_price, profit_loss=profit_loss, pricing_mode=sell_mode, result="FAILED", error=error, bid=pr.get("bid"), ask=pr.get("ask"), limit_price=sell_limit, price_buffer=SELL_BUFFER, client_order_id=order_result.get("client_order_id"))
        return {"success": False, "message": "Webull Sandbox LIMIT SELL was NOT accepted", "contract": contract_symbol, "limit_price_submitted": sell_limit, "pricing_mode": sell_mode, "bid": pr.get("bid"), "ask": pr.get("ask"), "order": order_result, "http_status": 502}

    client_order_id = order_result.get("client_order_id")
    update_trade(
        paper_trade["id"],
        open=1,
        state="PENDING_EXIT",
        result="PENDING_EXIT",
        exit_price=current_spy_price,
        exit_premium=exit_premium,
        exit_bid=pr.get("bid"),
        exit_ask=pr.get("ask"),
        exit_limit_price=sell_limit,
        exit_time=utc_now(),
        exit_order_id=order_result.get("response", {}).get("order_id") if isinstance(order_result.get("response"), dict) else None,
        exit_client_order_id=client_order_id,
        exit_order_status=order_result.get("order_status") or "ACCEPTED",
        profit_loss=profit_loss,
        pricing_mode=sell_mode,
    )

    journal_result = journal_trade(
        event="WEBULL_SELL_ACCEPTED",
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
        pricing_mode=sell_mode,
        result="PENDING_EXIT",
        state="PENDING_EXIT",
        bid=pr.get("bid"),
        ask=pr.get("ask"),
        limit_price=sell_limit,
        price_buffer=SELL_BUFFER,
        client_order_id=client_order_id,
        order_id=paper_trade.get("exit_order_id"),
        order_status=paper_trade.get("exit_order_status"),
    )

    # Reconcile once immediately. If the position is still present, the state
    # remains PENDING_EXIT. If it disappeared after a successful position
    # query, it becomes CLOSED.
    reconcile_after = _reconcile_active_trade(load_active_trade())
    final_trade = reconcile_after.get("trade") or load_active_trade()

    return {
        "success": True,
        "message": "Webull Sandbox LIMIT SELL accepted/submitted; fill status is not assumed.",
        "account": resolve_account(),
        "trade": final_trade,
        "order": order_result,
        "google_sheets": journal_result,
        "http_status": 200,
    }


# ============================================================
# Diagnostics / compatibility helpers
# ============================================================

def paper_trade_status():
    reconcile = _reconcile_active_trade()
    trade = reconcile.get("trade") or load_active_trade()
    webull = get_webull_positions()
    orphan_position = None
    if webull.get("success") and not trade:
        orphan_position = _find_single_long_option_position(webull.get("positions"))
    return {
        "success": reconcile.get("success", False) and webull.get("success", False),
        "open_trade": trade,
        "state": trade.get("state") if trade else "NONE",
        "account": resolve_account(),
        "webull_reconciliation": reconcile,
        "webull_positions": webull,
        "orphan_webull_position": orphan_position,
        "database_path": TRADE_DB,
        "source_of_truth": "WEBULL_PAPER_ACCOUNT",
    }


def debug_option_chain():
    contracts = get_option_contracts("CALL")
    return {"success": not (isinstance(contracts, dict) and "error" in contracts), "contracts": contracts}


def debug_market_data():
    return get_spy_price()


def test_options():
    spy_price = extract_spy_price()
    if spy_price is None:
        return {"success": False, "error": "Unable to get SPY price for option test"}
    call = _select_contract_with_spy_price("CALL", spy_price)
    time.sleep(1.5)
    put = _select_contract_with_spy_price("PUT", spy_price)
    return {"success": call.get("success", False) and put.get("success", False), "spy_price": spy_price, "call": call, "put": put}
