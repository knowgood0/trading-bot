import os
import json
import sqlite3
import urllib.request
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
# WEBULL ACCOUNT IDS
# ============================================================

CASH_ACCOUNT_ID = "DEN4YED3"
MARGIN_ACCOUNT_ID = "DEN8YFM7"


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


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


def load_open_trade():
    google_trade = get_open_trade_from_google_sheets()

    if google_trade:
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
            utc_now()
        )
    )

    connection.commit()
    connection.close()


def close_trade(
    trade_id,
    exit_price,
    exit_premium,
    profit_loss,
    pricing_mode
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
# GOOGLE SHEETS
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
                "User-Agent": "TradingBot/2.0"
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

    api_client = ApiClient(
        app_key,
        app_secret,
        "us"
    )

    api_client.add_endpoint(
        "us",
        "api.sandbox.webull.com"
    )

    trade_client = TradeClient(api_client)
    data_client = DataClient(api_client)

    return trade_client, data_client


def test_webull_connection():

    try:

        trade_client, _ = get_clients()

        response = (
            trade_client.account_v2.get_account_list()
        )

        return {
            "success": True,
            "status_code": response.status_code,
            "account": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# ACCOUNT DIAGNOSTIC
# ============================================================

def _query_account(account_id, account_name):

    result = {
        "account_name": account_name,
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
        "endpoint": "api.sandbox.webull.com",
        "accounts": {},
        "account_list": None,
        "account_list_status": None,
        "error": None
    }

    try:

        trade_client, _ = get_clients()

        # ----------------------------------------------------
        # ACCOUNT LIST
        # ----------------------------------------------------

        try:

            account_response = (
                trade_client.account_v2
                .get_account_list()
            )

            diagnostic["account_list_status"] = (
                account_response.status_code
            )

            diagnostic["account_list"] = (
                account_response.json()
            )

        except Exception as e:

            diagnostic["error"] = (
                "ACCOUNT LIST: " + str(e)
            )

        # ----------------------------------------------------
        # CASH ACCOUNT
        # ----------------------------------------------------

        diagnostic["accounts"]["cash"] = (
            _query_account(
                CASH_ACCOUNT_ID,
                "Individual Cash"
            )
        )

        # ----------------------------------------------------
        # MARGIN ACCOUNT
        # ----------------------------------------------------

        diagnostic["accounts"]["margin"] = (
            _query_account(
                MARGIN_ACCOUNT_ID,
                "Individual Margin"
            )
        )

        cash = diagnostic["accounts"]["cash"]
        margin = diagnostic["accounts"]["margin"]

        diagnostic["success"] = (
            cash.get("success")
            or margin.get("success")
        )

    except Exception as e:

        diagnostic["error"] = str(e)

    return diagnostic


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

def get_option_contracts(option_type="CALL"):

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
# PAPER BUY
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

    existing_trade = load_open_trade()

    if existing_trade:

        return {
            "success": False,
            "error":
                "A paper trade is already open",
            "trade":
                existing_trade
        }

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

    premium_result = get_option_price(
        contract_symbol
    )

    entry_premium = (
        premium_result.get(
            "premium"
        )
    )

    if entry_premium is not None:
        pricing_mode = "OPTION_PREMIUM"
    else:
        pricing_mode = "UNDERLYING_ONLY"

    entry_time = utc_now()

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
        "pricing_mode": pricing_mode,
        "result": "OPEN",
        "error": None
    }

    save_trade(trade)

    google_result = journal_trade(
        event="BUY",
        action="BUY",
        symbol="SPY",
        option_type=normalized_type,
        contract=contract_symbol,
        expiration=expiration,
        strike=strike,
        spy_price=spy_price,
        option_premium=entry_premium,
        entry_price=spy_price,
        pricing_mode=pricing_mode,
        result="OPEN",
        error=(
            premium_result.get("error")
            if entry_premium is None
            else ""
        )
    )

    return {
        "success": True,
        "message":
            "Paper BUY executed: "
            + normalized_type,
        "trade": trade,
        "google_sheets":
            google_result
    }


# ============================================================
# PAPER SELL
# ============================================================

def paper_sell_spy():

    paper_trade = load_open_trade()

    if not paper_trade:

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            result="FAILED",
            error="No open paper trade"
        )

        return {
            "success": False,
            "error":
                "No open paper trade"
        }

    current_spy_price = (
        extract_spy_price()
    )

    if current_spy_price is None:

        journal_trade(
            event="SELL_FAILED",
            action="SELL",
            symbol="SPY",
            option_type=paper_trade.get(
                "option_type",
                ""
            ),
            contract=paper_trade.get(
                "contract",
                ""
            ),
            result="FAILED",
            error=
                "Unable to get current SPY price"
        )

        return {
            "success": False,
            "error":
                "Unable to get current SPY price"
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

    premium_result = get_option_price(
        contract_symbol
    )

    exit_premium = (
        premium_result.get(
            "premium"
        )
    )

    entry_premium = (
        paper_trade.get(
            "entry_premium"
        )
    )

    if (
        entry_premium is not None
        and exit_premium is not None
        and entry_premium != 0
    ):

        profit_loss = (
            (
                exit_premium
                - entry_premium
            )
            / entry_premium
        ) * 100

        pricing_mode = (
            "OPTION_PREMIUM"
        )

    else:

        entry_spy_price = (
            paper_trade.get(
                "entry_price"
            )
        )

        if (
            entry_spy_price is None
            or entry_spy_price == 0
        ):

            return {
                "success": False,
                "error":
                    "Missing SPY entry price"
            }

        option_type = str(
            paper_trade.get(
                "option_type",
                "CALL"
            )
        ).upper()

        if option_type == "PUT":

            profit_loss = (
                (
                    entry_spy_price
                    - current_spy_price
                )
                / entry_spy_price
            ) * 100

        else:

            profit_loss = (
                (
                    current_spy_price
                    - entry_spy_price
                )
                / entry_spy_price
            ) * 100

        pricing_mode = (
            "UNDERLYING_ONLY"
        )

    profit_loss = round(
        profit_loss,
        2
    )

    google_result = (
        update_google_trade_closed(
            contract=contract_symbol,
            exit_price=current_spy_price,
            exit_premium=exit_premium,
            profit_loss=profit_loss,
            pricing_mode=pricing_mode,
            result="CLOSED",
            error=(
                premium_result.get(
                    "error"
                )
                if exit_premium is None
                else ""
            )
        )
    )

    if not google_result.get(
        "success"
    ):

        return {
            "success": False,
            "error":
                "Google Sheets failed to record "
                "the sell. Trade remains OPEN.",
            "google_sheets":
                google_result
        }

    local_trade_id = (
        paper_trade.get("id")
    )

    if local_trade_id is not None:

        try:

            close_trade(
                local_trade_id,
                current_spy_price,
                exit_premium,
                profit_loss,
                pricing_mode
            )

        except Exception:

            pass

    return {
        "success": True,
        "message":
            "Paper SELL executed",
        "trade": {
            "contract":
                contract_symbol,

            "option_type":
                paper_trade.get(
                    "option_type"
                ),

            "entry_price":
                paper_trade.get(
                    "entry_price"
                ),

            "entry_premium":
                entry_premium,

            "exit_price":
                current_spy_price,

            "exit_premium":
                exit_premium,

            "profit_loss":
                profit_loss,

            "pricing_mode":
                pricing_mode,

            "result":
                "CLOSED"
        },

        "google_sheets":
            google_result
    }


# ============================================================
# DEBUG / TEST HELPERS
# ============================================================

def get_persistent_open_trade():

    return get_open_trade_from_google_sheets()


def test_google_sheets_connection():

    trade = get_open_trade_from_google_sheets()

    return {
        "success": True,
        "open_trade": trade
    }


def paper_trade_status():

    trade = load_open_trade()

    return {
        "success": True,
        "open_trade": trade
    }


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
