import os
import json
import sqlite3
import urllib.request
import uuid
import time
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
# WEBULL SANDBOX
# ============================================================

WEBULL_ENDPOINT = "api.sandbox.webull.com"

# Account number, NOT API account ID.
# The bot will resolve this to the real API account_id
# from Webull's account list.
DEFAULT_ACCOUNT_NUMBER = "DEN8YFM7"

# Can be overridden in Render with:
# WEBULL_ACCOUNT_NUMBER=DEN8YFM7
#
# Cash account would be:
# WEBULL_ACCOUNT_NUMBER=DEN4YED3


# ============================================================
# TIME / IDS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def make_client_order_id(prefix="BOT"):
    """
    Webull client_order_id maximum length is 32 characters.
    """
    return (
        prefix
        + datetime.now(timezone.utc).strftime("%m%d%H%M%S")
        + uuid.uuid4().hex[:10]
    )[:32]


# ============================================================
# LOCAL SQLITE DATABASE
# ============================================================

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
            created_at TEXT,
            account_id TEXT,
            account_number TEXT,
            buy_order_id TEXT,
            buy_client_order_id TEXT,
            sell_order_id TEXT,
            sell_client_order_id TEXT
        )
        """
    )

    # Add newer columns if the database already existed.
    existing_columns = set()

    try:
        rows = connection.execute(
            "PRAGMA table_info(paper_trades)"
        ).fetchall()

        for row in rows:
            existing_columns.add(row["name"])

    except Exception:
        pass

    new_columns = {
        "account_id": "TEXT",
        "account_number": "TEXT",
        "buy_order_id": "TEXT",
        "buy_client_order_id": "TEXT",
        "sell_order_id": "TEXT",
        "sell_client_order_id": "TEXT"
    }

    for column_name, column_type in new_columns.items():

        if column_name not in existing_columns:

            try:
                connection.execute(
                    f"ALTER TABLE paper_trades ADD COLUMN "
                    f"{column_name} {column_type}"
                )
            except Exception:
                pass

    connection.commit()
    connection.close()


def _row_to_dict(row):

    if row is None:
        return None

    result = {
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

    # Newer columns may not exist in very old databases.
    for key in (
        "account_id",
        "account_number",
        "buy_order_id",
        "buy_client_order_id",
        "sell_order_id",
        "sell_client_order_id"
    ):

        try:
            result[key] = row[key]
        except Exception:
            result[key] = None

    return result


def load_local_open_trade():

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

    return _row_to_dict(row)


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
            created_at,
            account_id,
            account_number,
            buy_order_id,
            buy_client_order_id,
            sell_order_id,
            sell_client_order_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            trade.get("account_id"),
            trade.get("account_number"),
            trade.get("buy_order_id"),
            trade.get("buy_client_order_id"),
            trade.get("sell_order_id"),
            trade.get("sell_client_order_id")
        )
    )

    connection.commit()
    connection.close()


def update_buy_order_ids(
    trade_id,
    order_id,
    client_order_id
):

    _ensure_database()

    connection = _connect_db()

    connection.execute(
        """
        UPDATE paper_trades
        SET
            buy_order_id = ?,
            buy_client_order_id = ?
        WHERE id = ?
        """,
        (
            order_id,
            client_order_id,
            trade_id
        )
    )

    connection.commit()
    connection.close()


def close_trade(
    trade_id,
    exit_price,
    exit_premium,
    profit_loss,
    pricing_mode,
    sell_order_id=None,
    sell_client_order_id=None
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
            result = 'CLOSED',
            sell_order_id = ?,
            sell_client_order_id = ?
        WHERE id = ?
        """,
        (
            exit_price,
            exit_premium,
            profit_loss,
            pricing_mode,
            sell_order_id,
            sell_client_order_id,
            trade_id
        )
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
        (limit,)
    ).fetchall()

    connection.close()

    return [_row_to_dict(row) for row in rows]


# ============================================================
# GOOGLE SHEETS JOURNAL
# ============================================================

def send_to_google_sheets(data):

    try:

        payload = json.dumps(data).encode("utf-8")

        request = urllib.request.Request(
            GOOGLE_SHEETS_URL,
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            response_body = response.read().decode("utf-8")

        try:
            return json.loads(response_body)

        except Exception:

            return {
                "success": True,
                "response": response_body
            }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def get_open_trade_from_google_sheets():

    try:

        url = GOOGLE_SHEETS_URL + "?action=get_open_trade"

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TradingBot/3.0"
            },
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            response_body = response.read().decode("utf-8")

        result = json.loads(response_body)

        if not result.get("success"):
            return None

        trade = result.get("trade")

        if not trade:
            return None

        return trade

    except Exception:

        return None


def update_google_trade_closed(
    contract,
    exit_price,
    exit_premium,
    profit_loss,
    pricing_mode,
    result="CLOSED",
    error=""
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
            "timestamp": utc_now()
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
    error=""
):

    data = {
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
        "error": error
    }

    return send_to_google_sheets(data)


# ============================================================
# WEBULL CONNECTION
# ============================================================

def get_clients():

    app_key = os.environ.get("WEBULL_APP_KEY")
    app_secret = os.environ.get("WEBULL_APP_SECRET")

    if not app_key or not app_secret:

        raise RuntimeError(
            "WEBULL_APP_KEY and WEBULL_APP_SECRET "
            "must be configured in Render environment variables"
        )

    api_client = ApiClient(
        app_key,
        app_secret,
        "us"
    )

    api_client.add_endpoint(
        "us",
        WEBULL_ENDPOINT
    )

    trade_client = TradeClient(api_client)
    data_client = DataClient(api_client)

    return trade_client, data_client


# ============================================================
# WEBULL ACCOUNT RESOLUTION
# ============================================================

def get_webull_account_list():

    trade_client, _ = get_clients()

    response = (
        trade_client.account_v2.get_account_list()
    )

    data = response.json()

    return response, data


def resolve_account():

    requested_account_number = os.environ.get(
        "WEBULL_ACCOUNT_NUMBER",
        DEFAULT_ACCOUNT_NUMBER
    )

    response, data = get_webull_account_list()

    if response.status_code != 200:

        raise RuntimeError(
            "Webull account list failed: HTTP "
            + str(response.status_code)
            + " "
            + json.dumps(data)
        )

    if not isinstance(data, list):

        raise RuntimeError(
            "Unexpected Webull account list response: "
            + json.dumps(data)
        )

    for account in data:

        if str(
            account.get("account_number", "")
        ) == str(requested_account_number):

            api_account_id = account.get(
                "account_id"
            )

            if not api_account_id:

                raise RuntimeError(
                    "Webull returned account "
                    + str(requested_account_number)
                    + " without an account_id"
                )

            return {
                "account_id": api_account_id,
                "account_number":
                    account.get("account_number"),
                "account_name":
                    account.get("account_label")
                    or account.get("account_name")
                    or "",
                "account_class":
                    account.get("account_class"),
                "account_type":
                    account.get("account_type"),
                "user_id":
                    account.get("user_id")
            }

    available = []

    for account in data:

        available.append(
            {
                "account_id":
                    account.get("account_id"),
                "account_number":
                    account.get("account_number"),
                "account_label":
                    account.get("account_label"),
                "account_class":
                    account.get("account_class"),
                "account_type":
                    account.get("account_type")
            }
        )

    raise RuntimeError(
        "Requested Webull account number "
        + str(requested_account_number)
        + " was not found. Available accounts: "
        + json.dumps(available)
    )


# ============================================================
# WEBULL CONNECTION TEST
# ============================================================

def test_webull_connection():

    try:

        response, data = get_webull_account_list()

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "environment": "SANDBOX",
            "endpoint": WEBULL_ENDPOINT,
            "account": data
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# ACCOUNT DIAGNOSTIC
# ============================================================

def _query_account(
    account_id,
    account_name,
    account_number=""
):

    result = {
        "account_name": account_name,
        "account_number": account_number,
        "account_id": account_id,
        "balance": None,
        "positions": None,
        "balance_status": None,
        "positions_status": None,
        "errors": []
    }

    try:

        trade_client, _ = get_clients()

        # ----------------------------------------------------
        # BALANCE
        # ----------------------------------------------------

        try:

            balance_response = (
                trade_client.account_v2
                .get_account_balance(account_id)
            )

            result["balance_status"] = (
                balance_response.status_code
            )

            result["balance"] = (
                balance_response.json()
            )

        except Exception as e:

            result["errors"].append(
                "BALANCE: " + str(e)
            )

        # ----------------------------------------------------
        # POSITIONS
        # ----------------------------------------------------

        try:

            position_response = (
                trade_client.account_v2
                .get_account_position(account_id)
            )

            result["positions_status"] = (
                position_response.status_code
            )

            result["positions"] = (
                position_response.json()
            )

        except Exception as e:

            result["errors"].append(
                "POSITIONS: " + str(e)
            )

    except Exception as e:

        result["errors"].append(
            "CLIENT: " + str(e)
        )

    result["success"] = (
        result["balance_status"] == 200
        or result["positions_status"] == 200
    )

    return result


def account_diagnostic():

    diagnostic = {
        "success": False,
        "environment": "SANDBOX",
        "endpoint": WEBULL_ENDPOINT,
        "selected_account": None,
        "accounts": {},
        "account_list": None,
        "account_list_status": None,
        "error": None
    }

    try:

        response, account_list = (
            get_webull_account_list()
        )

        diagnostic["account_list_status"] = (
            response.status_code
        )

        diagnostic["account_list"] = account_list

        selected = resolve_account()

        diagnostic["selected_account"] = selected

        diagnostic["accounts"]["selected"] = (
            _query_account(
                selected["account_id"],
                selected["account_name"],
                selected["account_number"]
            )
        )

        diagnostic["success"] = (
            diagnostic["accounts"]["selected"].get(
                "success"
            )
        )

    except Exception as e:

        diagnostic["error"] = str(e)

    return diagnostic


# ============================================================
# ACCOUNT POSITIONS
# ============================================================

def get_webull_positions():

    try:

        account = resolve_account()

        trade_client, _ = get_clients()

        response = (
            trade_client.account_v2
            .get_account_position(
                account["account_id"]
            )
        )

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "account": account,
            "positions": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# POSITION HELPERS
# ============================================================

def _find_position_by_symbol(
    data,
    target_symbol
):

    if isinstance(data, list):

        for item in data:

            found = _find_position_by_symbol(
                item,
                target_symbol
            )

            if found:
                return found

        return None

    if not isinstance(data, dict):
        return None

    symbol = (
        data.get("symbol")
        or data.get("ticker")
        or data.get("instrument_symbol")
    )

    if symbol and str(symbol).upper() == str(
        target_symbol
    ).upper():

        return data

    for value in data.values():

        found = _find_position_by_symbol(
            value,
            target_symbol
        )

        if found:
            return found

    return None


def _extract_position_quantity(position):

    if not isinstance(position, dict):
        return 0.0

    for field in (
        "available_quantity",
        "available_qty",
        "quantity",
        "qty",
        "position",
        "total_quantity",
        "long_quantity"
    ):

        value = position.get(field)

        if value is not None:

            try:
                return float(value)

            except Exception:
                continue

    return 0.0


def get_webull_option_position(
    contract_symbol
):

    result = get_webull_positions()

    if not result.get("success"):

        return result

    position = _find_position_by_symbol(
        result.get("positions"),
        contract_symbol
    )

    quantity = _extract_position_quantity(
        position
    )

    return {
        "success": True,
        "account": result.get("account"),
        "contract": contract_symbol,
        "position": position,
        "quantity": quantity,
        "has_position": quantity > 0
    }


def account_has_spy_option_position():

    result = get_webull_positions()

    if not result.get("success"):
        return result

    found = []

    def scan(data):

        if isinstance(data, list):

            for item in data:
                scan(item)

            return

        if not isinstance(data, dict):
            return

        symbol = (
            data.get("symbol")
            or data.get("ticker")
            or data.get("instrument_symbol")
        )

        if (
            symbol
            and str(symbol).upper().startswith("SPY")
        ):

            quantity = _extract_position_quantity(
                data
            )

            if quantity > 0:

                found.append(
                    {
                        "symbol": symbol,
                        "quantity": quantity,
                        "position": data
                    }
                )

        for value in data.values():
            scan(value)

    scan(result.get("positions"))

    return {
        "success": True,
        "account": result.get("account"),
        "has_spy_option_position": bool(found),
        "positions": found
    }


# ============================================================
# SPY PRICE
# ============================================================

def get_spy_price():

    try:

        _, data_client = get_clients()

        response = data_client.market_data.get_snapshot(
            "SPY",
            Category.US_STOCK.name
        )

        return {
            "success": True,
            "data": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def extract_spy_price():

    result = get_spy_price()

    if not result.get("success"):
        return None

    data = result.get("data")

    try:

        if isinstance(data, list) and len(data) > 0:
            return float(data[0]["price"])

        if isinstance(data, dict):
            return float(data["price"])

    except Exception:
        return None

    return None


# ============================================================
# OPTION CONTRACTS
# ============================================================

def get_option_contracts(
    option_type="CALL"
):

    try:

        _, data_client = get_clients()

        today = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")

        normalized_type = str(
            option_type
        ).upper()

        if normalized_type not in (
            "CALL",
            "PUT"
        ):

            return {
                "error":
                    "Invalid option type: "
                    + normalized_type
            }

        response = (
            data_client.instrument
            .get_option_contracts(
                category=Category.US_OPTION.name,
                underlying_symbols="SPY",
                status="LISTING",
                start_date=today,
                end_date=today,
                option_type=normalized_type,
                style="AMERICAN",
                page_size=1000
            )
        )

        result = response.json()

        if isinstance(result, dict):

            if (
                "data" in result
                and isinstance(
                    result["data"],
                    list
                )
            ):

                return result["data"]

            if (
                "items" in result
                and isinstance(
                    result["items"],
                    list
                )
            ):

                return result["items"]

        return result

    except Exception as e:

        return {
            "error": str(e)
        }


def select_0dte_atm_contract(
    option_type="CALL"
):

    try:

        normalized_type = str(
            option_type
        ).upper()

        if normalized_type not in (
            "CALL",
            "PUT"
        ):

            return {
                "success": False,
                "error":
                    "Option type must be CALL or PUT"
            }

        contracts = get_option_contracts(
            normalized_type
        )

        if (
            isinstance(contracts, dict)
            and "error" in contracts
        ):

            return {
                "success": False,
                "error": contracts["error"]
            }

        if not isinstance(
            contracts,
            list
        ):

            return {
                "success": False,
                "error":
                    "Unexpected option contract response"
            }

        spy_price = extract_spy_price()

        if spy_price is None:

            return {
                "success": False,
                "error":
                    "Unable to get current SPY price"
            }

        today = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d")

        valid = []

        for contract in contracts:

            try:

                expiration = (
                    contract.get(
                        "expiration_date"
                    )
                    or contract.get(
                        "expiration"
                    )
                    or ""
                )

                if isinstance(
                    expiration,
                    str
                ):

                    expiration = expiration[:10]

                strike_value = contract.get(
                    "strike_price"
                )

                if strike_value is None:
                    continue

                strike = float(
                    strike_value
                )

                contract_type = str(
                    contract.get(
                        "option_type"
                    )
                    or ""
                ).upper()

                def_type = str(
                    contract.get(
                        "def_type"
                    )
                    or ""
                ).upper()

                style = str(
                    contract.get(
                        "style"
                    )
                    or ""
                ).upper()

                tradable_status = str(
                    contract.get(
                        "tradable_status"
                    )
                    or ""
                ).upper()

                if (
                    def_type == "STANDARD"
                    and style == "AMERICAN"
                    and tradable_status == "OC"
                    and contract_type == normalized_type
                    and expiration == today
                ):

                    valid.append(
                        contract
                    )

            except Exception:
                continue

        if not valid:

            return {
                "success": False,
                "error":
                    "No valid 0DTE "
                    + normalized_type
                    + " contracts found for today"
            }

        valid.sort(
            key=lambda x:
                abs(
                    float(
                        x["strike_price"]
                    )
                    - spy_price
                )
        )

        selected = valid[0]

        return {
            "success": True,
            "spy_price": spy_price,
            "selected_contract": {
                "symbol":
                    selected.get("symbol"),

                "type":
                    normalized_type,

                "strike":
                    selected.get(
                        "strike_price"
                    ),

                "expiration":
                    (
                        selected.get(
                            "expiration_date"
                        )
                        or selected.get(
                            "expiration"
                        )
                    ),

                "raw":
                    selected
            }
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def select_contract(
    option_type="CALL"
):

    return select_0dte_atm_contract(
        option_type
    )


# ============================================================
# OPTION PRICING
# ============================================================

def get_option_price(
    option_symbol
):

    try:

        _, data_client = get_clients()

        response = (
            data_client.option_market_data
            .get_option_snapshot(
                option_symbol,
                Category.US_OPTION.name
            )
        )

        data = response.json()

        if (
            isinstance(data, list)
            and data
        ):

            item = data[0]

        elif isinstance(data, dict):

            item = data

        else:

            item = {}

        premium = None

        for field in (
            "latest_price",
            "last_price",
            "price",
            "last",
            "close",
            "mark_price"
        ):

            if item.get(field) is not None:

                premium = float(
                    item[field]
                )

                break

        return {
            "success": True,
            "premium": premium,
            "data": data
        }

    except Exception as e:

        return {
            "success": False,
            "premium": None,
            "error": str(e)
        }


# ============================================================
# WEBULL ORDER HELPERS
# ============================================================

def _place_option_order(
    account_id,
    contract_symbol,
    option_type,
    expiration,
    strike,
    side,
    limit_price,
    position_intent
):

    trade_client, _ = get_clients()

    client_order_id = make_client_order_id(
        "BOT"
    )

    order = {
        "client_order_id": client_order_id,
        "combo_type": "NORMAL",
        "option_strategy": "SINGLE",
        "instrument_type": "OPTION",
        "entrust_type": "QTY",
        "symbol": contract_symbol,
        "market": "US",
        "side": side,
        "order_type": "LIMIT",
        "time_in_force": "DAY",
        "limit_price": str(
            round(float(limit_price), 2)
        ),
        "quantity": "1",
        "position_intent": position_intent,
        "legs": [
            {
                "instrument_type": "OPTION",
                "market": "US",
                "symbol": contract_symbol,
                "side": side,
                "quantity": "1",
                "option_expire_date":
                    str(expiration)[:10],
                "option_type": option_type,
                "strike_price": str(
                    strike
                )
            }
        ]
    }

    # Current Webull Python SDK supports the V2 option
    # order operation. The exact method is used here rather
    # than manually generating API signatures.
    order_v2 = getattr(
        trade_client,
        "order_v2",
        None
    )

    if order_v2 is None:

        raise RuntimeError(
            "Webull SDK does not expose order_v2. "
            "Installed SDK may be outdated."
        )

    place_option = getattr(
        order_v2,
        "place_option",
        None
    )

    place_order = getattr(
        order_v2,
        "place_order",
        None
    )

    response = None

    # Prefer the SDK's dedicated option method.
    if callable(place_option):

        try:

            response = place_option(
                account_id,
                [order]
            )

        except TypeError:

            response = place_option(
                account_id,
                order
            )

    elif callable(place_order):

        try:

            response = place_order(
                account_id,
                [order]
            )

        except TypeError:

            response = place_order(
                account_id,
                order
            )

    else:

        raise RuntimeError(
            "Webull SDK does not expose an option "
            "place-order method. Installed SDK may "
            "be outdated."
        )

    status_code = getattr(
        response,
        "status_code",
        None
    )

    try:
        body = response.json()
    except Exception:
        body = str(response)

    success = (
        status_code is not None
        and 200 <= status_code < 300
    )

    return {
        "success": success,
        "status_code": status_code,
        "client_order_id": client_order_id,
        "order_request": order,
        "response": body
    }


def _extract_order_id(response_data):

    if not isinstance(
        response_data,
        dict
    ):
        return None

    for key in (
        "order_id",
        "orderId"
    ):

        if response_data.get(key):
            return response_data.get(key)

    orders = response_data.get(
        "orders"
    )

    if isinstance(
        orders,
        list
    ):

        for order in orders:

            if isinstance(order, dict):

                if order.get("order_id"):
                    return order.get(
                        "order_id"
                    )

    return None


def get_order_detail(
    client_order_id
):

    try:

        account = resolve_account()

        trade_client, _ = get_clients()

        order_v2 = getattr(
            trade_client,
            "order_v2",
            None
        )

        if order_v2 is None:

            return {
                "success": False,
                "error":
                    "Webull SDK does not expose order_v2"
            }

        method = getattr(
            order_v2,
            "get_order_detail",
            None
        )

        if not callable(method):

            return {
                "success": False,
                "error":
                    "Webull SDK does not expose "
                    "get_order_detail"
            }

        response = method(
            account["account_id"],
            client_order_id
        )

        try:
            body = response.json()
        except Exception:
            body = str(response)

        return {
            "success":
                200 <= response.status_code < 300,
            "status_code":
                response.status_code,
            "account":
                account,
            "client_order_id":
                client_order_id,
            "order":
                body
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# ACTUAL WEBULL PAPER BUY
# ============================================================

def paper_buy_spy(
    option_type="CALL"
):

    normalized_type = str(
        option_type
    ).upper()

    if normalized_type not in (
        "CALL",
        "PUT"
    ):

        return {
            "success": False,
            "error":
                "Option type must be CALL or PUT"
        }

    # --------------------------------------------------------
    # Resolve the actual Webull API account ID.
    # --------------------------------------------------------

    try:

        account = resolve_account()

    except Exception as e:

        error = str(e)

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            result="FAILED",
            error=error
        )

        return {
            "success": False,
            "error": error
        }

    # --------------------------------------------------------
    # Webull is now the source of truth.
    # Do NOT use Google Sheets to decide whether a position
    # exists.
    # --------------------------------------------------------

    position_check = (
        account_has_spy_option_position()
    )

    if not position_check.get("success"):

        error = (
            "Unable to verify Webull positions "
            "before BUY: "
            + str(
                position_check.get("error")
            )
        )

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            result="FAILED",
            error=error
        )

        return {
            "success": False,
            "error": error,
            "webull":
                position_check
        }

    if position_check.get(
        "has_spy_option_position"
    ):

        error = (
            "Webull already shows an open SPY "
            "option position. BUY blocked."
        )

        journal_trade(
            event="BUY_BLOCKED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            result="BLOCKED",
            error=error
        )

        return {
            "success": False,
            "error": error,
            "webull_positions":
                position_check.get(
                    "positions"
                )
        }

    # --------------------------------------------------------
    # Select 0DTE ATM contract.
    # --------------------------------------------------------

    contract_result = (
        select_0dte_atm_contract(
            normalized_type
        )
    )

    if not contract_result.get(
        "success"
    ):

        error = contract_result.get(
            "error",
            "Contract selection failed"
        )

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=normalized_type,
            result="FAILED",
            error=error
        )

        return contract_result

    selected = (
        contract_result[
            "selected_contract"
        ]
    )

    spy_price = (
        contract_result.get(
            "spy_price"
        )
    )

    contract_symbol = (
        selected.get("symbol")
    )

    expiration = (
        selected.get("expiration")
    )

    strike = (
        selected.get("strike")
    )

    # --------------------------------------------------------
    # Get current option premium.
    # --------------------------------------------------------

    premium_result = get_option_price(
        contract_symbol
    )

    entry_premium = (
        premium_result.get(
            "premium"
        )
    )

    if entry_premium is None:

        error = (
            "Unable to obtain a current option "
            "premium. Webull BUY was NOT submitted."
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
            error=error
        )

        return {
            "success": False,
            "error": error,
            "premium_data":
                premium_result
        }

    if entry_premium <= 0:

        error = (
            "Invalid option premium: "
            + str(entry_premium)
        )

        return {
            "success": False,
            "error": error
        }

    limit_price = round(
        float(entry_premium),
        2
    )

    # --------------------------------------------------------
    # ACTUAL WEBULL PAPER ORDER.
    # --------------------------------------------------------

    try:

        order_result = _place_option_order(
            account_id=account["account_id"],
            contract_symbol=contract_symbol,
            option_type=normalized_type,
            expiration=expiration,
            strike=strike,
            side="BUY",
            limit_price=limit_price,
            position_intent="BUY_TO_OPEN"
        )

    except Exception as e:

        error = (
            "Webull BUY submission error: "
            + str(e)
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
            option_premium=entry_premium,
            result="FAILED",
            error=error
        )

        return {
            "success": False,
            "error": error
        }

    if not order_result.get("success"):

        error = (
            "Webull rejected/failed the BUY order."
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
            option_premium=entry_premium,
            result="FAILED",
            error=json.dumps(
                order_result
            )
        )

        return {
            "success": False,
            "error": error,
            "webull_order":
                order_result
        }

    response_body = (
        order_result.get(
            "response"
        )
    )

    order_id = _extract_order_id(
        response_body
    )

    client_order_id = (
        order_result.get(
            "client_order_id"
        )
    )

    # --------------------------------------------------------
    # Only now create the local backup record.
    # --------------------------------------------------------

    trade = {
        "open": True,
        "contract": contract_symbol,
        "option_type": normalized_type,
        "expiration": expiration,
        "strike": strike,
        "entry_price": spy_price,
        "entry_premium": entry_premium,
        "entry_time": utc_now(),
        "exit_price": None,
        "exit_premium": None,
        "profit_loss": None,
        "pricing_mode": "OPTION_PREMIUM",
        "result": "OPEN",
        "error": None,
        "account_id":
            account["account_id"],
        "account_number":
            account["account_number"],
        "buy_order_id":
            order_id,
        "buy_client_order_id":
            client_order_id
    }

    save_trade(trade)

    # --------------------------------------------------------
    # Google Sheets is backup journaling only.
    # Failure here does NOT invalidate the Webull trade.
    # --------------------------------------------------------

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
        result="SUBMITTED",
        error=""
    )

    return {
        "success": True,
        "message":
            "Webull Sandbox BUY submitted",
        "account": account,
        "trade": trade,
        "webull_order":
            order_result,
        "order_id":
            order_id,
        "client_order_id":
            client_order_id,
        "google_sheets":
            google_result
    }


# ============================================================
# ACTUAL WEBULL PAPER SELL
# ============================================================

def paper_sell_spy():

    # --------------------------------------------------------
    # Local SQLite is used only to remember which contract
    # this bot bought. Webull remains the authority on whether
    # the position actually exists.
    # --------------------------------------------------------

    paper_trade = load_local_open_trade()

    if not paper_trade:

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            result="FAILED",
            error=
                "No local trade record identifying "
                "the contract to close"
        )

        return {
            "success": False,
            "error":
                "No local trade record identifying "
                "the contract to close"
        }

    contract_symbol = (
        paper_trade.get(
            "contract"
        )
    )

    if not contract_symbol:

        return {
            "success": False,
            "error":
                "Open trade is missing contract symbol"
        }

    option_type = str(
        paper_trade.get(
            "option_type",
            "CALL"
        )
    ).upper()

    expiration = paper_trade.get(
        "expiration"
    )

    strike = paper_trade.get(
        "strike"
    )

    # --------------------------------------------------------
    # Resolve Webull account.
    # --------------------------------------------------------

    try:

        account = resolve_account()

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

    # --------------------------------------------------------
    # Verify the actual Webull position exists.
    # --------------------------------------------------------

    position_result = (
        get_webull_option_position(
            contract_symbol
        )
    )

    if not position_result.get(
        "success"
    ):

        return {
            "success": False,
            "error":
                "Unable to verify Webull position "
                "before SELL",
            "webull":
                position_result
        }

    if not position_result.get(
        "has_position"
    ):

        error = (
            "Webull does not currently show the "
            "expected position: "
            + contract_symbol
        )

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            option_type=option_type,
            contract=contract_symbol,
            result="FAILED",
            error=error
        )

        return {
            "success": False,
            "error": error,
            "webull":
                position_result
        }

    webull_quantity = (
        position_result.get(
            "quantity",
            0
        )
    )

    if webull_quantity < 1:

        return {
            "success": False,
            "error":
                "Webull position quantity is less than 1",
            "webull":
                position_result
        }

    # We deliberately close only one contract because the bot
    # opens only one contract.
    quantity_to_sell = 1

    # --------------------------------------------------------
    # Get current option price.
    # --------------------------------------------------------

    premium_result = get_option_price(
        contract_symbol
    )

    exit_premium = (
        premium_result.get(
            "premium"
        )
    )

    if exit_premium is None:

        return {
            "success": False,
            "error":
                "Unable to obtain current option "
                "premium. Webull SELL was NOT submitted.",
            "premium_data":
                premium_result
        }

    if exit_premium <= 0:

        return {
            "success": False,
            "error":
                "Invalid exit option premium: "
                + str(exit_premium)
        }

    limit_price = round(
        float(exit_premium),
        2
    )

    current_spy_price = (
        extract_spy_price()
    )

    # --------------------------------------------------------
    # Calculate backup-log P/L.
    #
    # This does NOT control the trade.
    # Webull controls the actual position.
    # --------------------------------------------------------

    entry_premium = (
        paper_trade.get(
            "entry_premium"
        )
    )

    if (
        entry_premium is not None
        and entry_premium != 0
    ):

        profit_loss_percent = (
            (
                exit_premium
                - float(entry_premium)
            )
            / float(entry_premium)
        ) * 100

        # One contract = 100 shares of option exposure.
        profit_loss_dollars = (
            (
                exit_premium
                - float(entry_premium)
            )
            * 100
            * quantity_to_sell
        )

    else:

        profit_loss_percent = None
        profit_loss_dollars = None

    # --------------------------------------------------------
    # ACTUAL WEBULL PAPER SELL.
    # --------------------------------------------------------

    try:

        order_result = _place_option_order(
            account_id=account["account_id"],
            contract_symbol=contract_symbol,
            option_type=option_type,
            expiration=expiration,
            strike=strike,
            side="SELL",
            limit_price=limit_price,
            position_intent="SELL_TO_CLOSE"
        )

    except Exception as e:

        error = (
            "Webull SELL submission error: "
            + str(e)
        )

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            option_type=option_type,
            contract=contract_symbol,
            result="FAILED",
            error=error
        )

        return {
            "success": False,
            "error": error
        }

    if not order_result.get(
        "success"
    ):

        error = (
            "Webull rejected/failed the SELL order."
        )

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            option_type=option_type,
            contract=contract_symbol,
            result="FAILED",
            error=json.dumps(
                order_result
            )
        )

        return {
            "success": False,
            "error": error,
            "webull_order":
                order_result
        }

    response_body = (
        order_result.get(
            "response"
        )
    )

    order_id = _extract_order_id(
        response_body
    )

    client_order_id = (
        order_result.get(
            "client_order_id"
        )
    )

    # --------------------------------------------------------
    # Update local backup record.
    # --------------------------------------------------------

    local_trade_id = (
        paper_trade.get("id")
    )

    if local_trade_id is not None:

        try:

            close_trade(
                local_trade_id,
                current_spy_price,
                exit_premium,
                profit_loss_dollars,
                "OPTION_PREMIUM",
                sell_order_id=order_id,
                sell_client_order_id=
                    client_order_id
            )

        except Exception:

            pass

    google_result = (
        update_google_trade_closed(
            contract=contract_symbol,
            exit_price=current_spy_price,
            exit_premium=exit_premium,
            profit_loss=profit_loss_dollars,
            pricing_mode="OPTION_PREMIUM",
            result="SUBMITTED",
            error=""
        )
    )

    return {
        "success": True,
        "message":
            "Webull Sandbox SELL submitted",
        "account": account,
        "trade": {
            "contract":
                contract_symbol,
            "option_type":
                option_type,
            "entry_premium":
                entry_premium,
            "exit_premium":
                exit_premium,
            "profit_loss_dollars":
                profit_loss_dollars,
            "profit_loss_percent":
                (
                    round(
                        profit_loss_percent,
                        2
                    )
                    if profit_loss_percent
                    is not None
                    else None
                ),
            "result":
                "CLOSE_ORDER_SUBMITTED"
        },
        "webull_order":
            order_result,
        "order_id":
            order_id,
        "client_order_id":
            client_order_id,
        "google_sheets":
            google_result
    }


# ============================================================
# PAPER STATUS
# ============================================================

def paper_trade_status():

    local_trade = load_local_open_trade()

    webull_result = get_webull_positions()

    return {
        "success": True,
        "source_of_truth":
            "WEBULL_SANDBOX",
        "webull":
            webull_result,
        "local_backup_trade":
            local_trade
    }


# ============================================================
# GOOGLE TEST
# ============================================================

def test_google_sheets_connection():

    trade = get_open_trade_from_google_sheets()

    return {
        "success": True,
        "open_trade": trade
    }


# ============================================================
# DEBUG / TEST HELPERS
# ============================================================

def debug_option_chain():

    contracts = get_option_contracts(
        "CALL"
    )

    return {
        "success": True,
        "contracts": contracts
    }


def debug_market_data():

    return get_spy_price()


def test_options():

    call = select_contract(
        "CALL"
    )

    put = select_contract(
        "PUT"
    )

    return {
        "success": True,
        "call": call,
        "put": put
    }


# ============================================================
# ORDER DETAIL TEST
# ============================================================

def test_order_detail(
    client_order_id
):

    return get_order_detail(
        client_order_id
    )
