import os
import json
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime

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
            datetime.now().isoformat()
        )
    )

    connection.commit()
    connection.close()


def close_trade(trade_id, exit_price, exit_premium, profit_loss, pricing_mode):
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

        with urllib.request.urlopen(request, timeout=15) as response:
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
        "timestamp": datetime.now().isoformat(),
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

        response = trade_client.account_v2.get_account_list()

        return {
            "success": True,
            "account": response.json()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


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


def get_option_contracts(option_type="CALL"):
    try:
        _, data_client = get_clients()

        today = datetime.now().strftime("%Y-%m-%d")

        response = data_client.instrument.get_option_contracts(
            category=Category.US_OPTION.name,
            underlying_symbols="SPY",
            status="LISTING",
            start_date=today,
            end_date=today,
            option_type=option_type,
            style="AMERICAN",
            page_size=1000
        )

        result = response.json()

        if isinstance(result, dict):
            if "data" in result and isinstance(result["data"], list):
                return result["data"]

            if "items" in result and isinstance(result["items"], list):
                return result["items"]

        return result

    except Exception as e:
        return {
            "error": str(e)
        }


def select_0dte_atm_contract(option_type="CALL"):
    try:
        contracts = get_option_contracts(option_type)

        if isinstance(contracts, dict) and "error" in contracts:
            return {
                "success": False,
                "error": contracts["error"]
            }

        if not isinstance(contracts, list):
            return {
                "success": False,
                "error": "Unexpected option contract response"
            }

        spy_price = extract_spy_price()

        if spy_price is None:
            return {
                "success": False,
                "error": "Unable to get current SPY price"
            }

        today = datetime.now().strftime("%Y-%m-%d")

        valid = []

        for contract in contracts:
            try:
                expiration = (
                    contract.get("expiration_date")
                    or contract.get("expiration")
                    or ""
                )

                if isinstance(expiration, str):
                    expiration = expiration[:10]

                strike = float(contract.get("strike_price"))

                contract_type = contract.get("option_type")

                if (
                    contract.get("def_type") == "STANDARD"
                    and contract.get("style") == "AMERICAN"
                    and contract.get("tradable_status") == "OC"
                    and contract_type == option_type
                    and expiration == today
                ):
                    valid.append(contract)

            except Exception:
                continue

        if not valid:
            return {
                "success": False,
                "error": "No valid 0DTE contracts found for today"
            }

        valid.sort(
            key=lambda x: abs(
                float(x["strike_price"]) - spy_price
            )
        )

        selected = valid[0]

        selected_symbol = selected.get("symbol")

        return {
            "success": True,
            "spy_price": spy_price,
            "selected_contract": {
                "symbol": selected_symbol,
                "type": selected.get("option_type"),
                "strike": selected.get("strike_price"),
                "expiration": (
                    selected.get("expiration_date")
                    or selected.get("expiration")
                ),
                "raw": selected
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_option_price(option_symbol):
    try:
        _, data_client = get_clients()

        response = data_client.option_market_data.get_option_snapshot(
            option_symbol,
            Category.US_OPTION.name
        )

        data = response.json()

        premium = None

        if isinstance(data, list) and data:
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            item = {}

        for field in (
            "latest_price",
            "last_price",
            "price",
            "last",
            "close",
            "mark_price"
        ):
            if item.get(field) is not None:
                premium = float(item[field])
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


def select_contract(option_type="CALL"):
    return select_0dte_atm_contract(option_type)


def paper_buy_spy(option_type="CALL"):
    existing_trade = load_open_trade()

    if existing_trade:
        return {
            "success": False,
            "error": "A paper trade is already open",
            "trade": existing_trade
        }

    contract_result = select_0dte_atm_contract(option_type)

    if not contract_result.get("success"):
        error = contract_result.get("error", "Contract selection failed")

        journal_trade(
            event="BUY_FAILED",
            action="BUY",
            symbol="SPY",
            option_type=option_type,
            result="FAILED",
            error=error
        )

        return contract_result

    selected = contract_result["selected_contract"]

    spy_price = contract_result.get("spy_price")

    contract_symbol = selected.get("symbol")
    expiration = selected.get("expiration")
    strike = selected.get("strike")

    premium_result = get_option_price(contract_symbol)

    entry_premium = premium_result.get("premium")

    if entry_premium is not None:
        pricing_mode = "OPTION_PREMIUM"
    else:
        pricing_mode = "UNDERLYING_ONLY"

    entry_time = datetime.now().isoformat()

    trade = {
        "open": True,
        "contract": contract_symbol,
        "option_type": option_type,
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

    saved_trade = load_latest_trade()

    google_result = journal_trade(
        event="BUY",
        action="BUY",
        symbol="SPY",
        option_type=option_type,
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
        "message": "Paper BUY executed",
        "trade": saved_trade,
        "google_sheets": google_result
    }


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
            "error": "No open paper trade"
        }

    current_spy_price = extract_spy_price()

    if current_spy_price is None:
        return {
            "success": False,
            "error": "Unable to get current SPY price"
        }

    contract_symbol = paper_trade.get("contract")

    premium_result = get_option_price(contract_symbol)

    exit_premium = premium_result.get("premium")

    entry_premium = paper_trade.get("entry_premium")

    if (
        entry_premium is not None
        and exit_premium is not None
        and entry_premium != 0
    ):
        profit_loss = (
            (exit_premium - entry_premium)
            / entry_premium
        ) * 100

        pricing_mode = "OPTION_PREMIUM"

    else:
        entry_spy_price = paper_trade.get("entry_price")

        if entry_spy_price is None or entry_spy_price == 0:
            return {
                "success": False,
                "error": "Missing SPY entry price"
            }

        profit_loss = (
            (current_spy_price - entry_spy_price)
            / entry_spy_price
        ) * 100

        pricing_mode = "UNDERLYING_ONLY"

    profit_loss = round(profit_loss, 
