import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category

ET = ZoneInfo("America/New_York")

DB_PATH = os.environ.get(
    "TRADE_DB_PATH",
    "paper_trades.db"
)

# NOTE: Render's filesystem is ephemeral on the free/standard tier - this
# SQLite file resets on every redeploy/restart unless a persistent disk is
# attached. Same limitation the old paper_trade.json had.


def get_db():

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            open INTEGER NOT NULL DEFAULT 0,
            contract_symbol TEXT,
            option_type TEXT,
            strike REAL,
            expiration_date TEXT,
            underlying_symbol TEXT,
            underlying_entry_price REAL,
            option_entry_price REAL,
            entry_time TEXT,
            underlying_exit_price REAL,
            option_exit_price REAL,
            exit_time TEXT,
            profit_loss REAL,
            profit_loss_percent REAL,
            pricing_mode TEXT,
            status TEXT
        )
        """
    )

    connection.commit()

    return connection


def row_to_trade(row):

    if row is None:

        return {
            "open": False,
            "contract": None,
            "entry_price": None,
            "entry_option_price": None,
            "entry_time": None,
            "exit_price": None,
            "exit_option_price": None,
            "exit_time": None,
            "profit_loss": None,
            "profit_loss_percent": None,
            "pricing_mode": "UNDERLYING_ONLY",
            "status": "NO_TRADE"
        }

    return {
        "id": row["id"],
        "open": bool(row["open"]),

        "contract": {
            "symbol": row["contract_symbol"],
            "type": row["option_type"],
            "strike": row["strike"],
            "expiration": row["expiration_date"],
            "underlying": row["underlying_symbol"]
        },

        "entry_price": row["underlying_entry_price"],
        "entry_option_price": row["option_entry_price"],
        "entry_time": row["entry_time"],

        "exit_price": row["underlying_exit_price"],
        "exit_option_price": row["option_exit_price"],
        "exit_time": row["exit_time"],

        "profit_loss": row["profit_loss"],
        "profit_loss_percent": row["profit_loss_percent"],

        "pricing_mode": row["pricing_mode"],
        "status": row["status"]
    }


def get_open_trade():

    connection = get_db()

    try:

        row = connection.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE open = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        return row_to_trade(row)

    finally:

        connection.close()


def get_latest_trade():

    connection = get_db()

    try:

        row = connection.execute(
            """
            SELECT *
            FROM paper_trades
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        return row_to_trade(row)

    finally:

        connection.close()


def save_trade(trade):

    contract = trade.get("contract") or {}

    connection = get_db()

    try:

        cursor = connection.execute(
            """
            INSERT INTO paper_trades (
                open,
                contract_symbol,
                option_type,
                strike,
                expiration_date,
                underlying_symbol,
                underlying_entry_price,
                option_entry_price,
                entry_time,
                underlying_exit_price,
                option_exit_price,
                exit_time,
                profit_loss,
                profit_loss_percent,
                pricing_mode,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1 if trade.get("open") else 0,
                contract.get("symbol"),
                contract.get("type"),
                contract.get("strike"),
                contract.get("expiration"),
                contract.get("underlying", "SPY"),
                trade.get("entry_price"),
                trade.get("entry_option_price"),
                trade.get("entry_time"),
                trade.get("exit_price"),
                trade.get("exit_option_price"),
                trade.get("exit_time"),
                trade.get("profit_loss"),
                trade.get("profit_loss_percent"),
                trade.get("pricing_mode", "UNDERLYING_ONLY"),
                trade.get("status", "UNKNOWN")
            )
        )

        connection.commit()

        trade["id"] = cursor.lastrowid

        return trade

    finally:

        connection.close()


def close_trade(trade):

    connection = get_db()

    try:

        connection.execute(
            """
            UPDATE paper_trades
            SET
                open = 0,
                underlying_exit_price = ?,
                option_exit_price = ?,
                exit_time = ?,
                profit_loss = ?,
                profit_loss_percent = ?,
                pricing_mode = ?,
                status = ?
            WHERE id = ?
            """,
            (
                trade.get("exit_price"),
                trade.get("exit_option_price"),
                trade.get("exit_time"),
                trade.get("profit_loss"),
                trade.get("profit_loss_percent"),
                trade.get("pricing_mode", "UNDERLYING_ONLY"),
                trade.get("status", "CLOSED"),
                trade.get("id")
            )
        )

        connection.commit()

    finally:

        connection.close()


def get_clients():

    app_key = os.environ.get("WEBULL_APP_KEY")
    app_secret = os.environ.get("WEBULL_APP_SECRET")

    if not app_key or not app_secret:

        raise RuntimeError(
            "WEBULL_APP_KEY and WEBULL_APP_SECRET must be configured"
        )

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


def get_option_contracts(option_type="CALL", expiration_date=None):

    try:

        _, data_client = get_clients()

        if expiration_date is None:

            expiration_date = datetime.now(ET).strftime("%Y-%m-%d")

        response = data_client.instrument.get_option_contracts(
            category=Category.US_OPTION.name,
            underlying_symbols="SPY",
            status="LISTING",
            start_date=expiration_date,
            end_date=expiration_date,
            option_type=option_type,
            style="AMERICAN",
            page_size=1000
        )

        return response.json()

    except Exception as e:

        return {
            "error": str(e)
        }


def select_0dte_atm_contract(option_type="CALL"):

    try:

        option_type = option_type.upper()

        expiration_date = datetime.now(ET).strftime("%Y-%m-%d")

        spy_price = extract_spy_price()

        if spy_price is None:

            return {
                "success": False,
                "error": "Unable to obtain current SPY price"
            }

        contracts = get_option_contracts(option_type, expiration_date)

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

        valid = []

        for contract in contracts:

            try:

                if contract.get("def_type") != "STANDARD":
                    continue

                if contract.get("style") != "AMERICAN":
                    continue

                if contract.get("tradable_status") != "OC":
                    continue

                if contract.get("option_type") != option_type:
                    continue

                if contract.get("expiration_date") != expiration_date:
                    continue

                strike = float(contract["strike_price"])

                valid.append((abs(strike - spy_price), strike, contract))

            except Exception:

                continue

        if not valid:

            return {
                "success": False,
                "error": (
                    "No valid 0DTE "
                    f"{option_type} contracts found "
                    f"for SPY expiring {expiration_date}"
                ),
                "spy_price": spy_price,
                "expiration_date": expiration_date
            }

        valid.sort(key=lambda item: (item[0], item[1]))

        distance, strike, selected = valid[0]

        return {
            "success": True,
            "spy_price": spy_price,
            "expiration_date": expiration_date,
            "distance_from_atm": round(distance, 4),
            "selected_contract": {
                "symbol": selected.get("symbol"),
                "type": selected.get("option_type"),
                "strike": selected.get("strike_price"),
                "expiration": selected.get("expiration_date"),
                "underlying": "SPY",
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

        return {
            "success": True,
            "data": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def extract_option_price(result):

    if not result:

        return None

    if not result.get("success"):

        return None

    data = result.get("data")

    try:

        if isinstance(data, list) and len(data) > 0:

            item = data[0]

        elif isinstance(data, dict):

            item = data

        else:

            return None

        price = item.get("price")

        if price not in (None, ""):

            return float(price)

    except Exception:

        pass

    return None


def paper_buy_spy(option_type="CALL"):

    existing = get_open_trade()

    if existing.get("open"):

        return {
            "success": False,
            "error": "A paper trade is already open",
            "trade": existing
        }

    contract_result = select_0dte_atm_contract(option_type)

    if not contract_result.get("success"):

        return contract_result

    contract = contract_result["selected_contract"]
    spy_price = contract_result["spy_price"]
    option_symbol = contract["symbol"]

    # Try to get a real option premium. If Webull's US_OPTION market-data
    # permission isn't available (current known limitation), fall back to
    # UNDERLYING_ONLY pricing instead of failing the whole trade - this
    # keeps data collection running continuously, and will start capturing
    # real premiums automatically the moment that permission is enabled,
    # with no redeploy needed.
    option_result = get_option_price(option_symbol)
    option_price = extract_option_price(option_result)

    now = datetime.now(ET).isoformat()

    if option_price is not None:

        trade = {
            "open": True,
            "contract": contract,
            "entry_price": spy_price,
            "entry_option_price": option_price,
            "entry_time": now,
            "exit_price": None,
            "exit_option_price": None,
            "exit_time": None,
            "profit_loss": None,
            "profit_loss_percent": None,
            "pricing_mode": "OPTION_PREMIUM",
            "status": "OPEN"
        }

        message = "Paper 0DTE ATM option BUY executed (OPTION_PREMIUM mode)"

    else:

        trade = {
            "open": True,
            "contract": contract,
            "entry_price": spy_price,
            "entry_option_price": None,
            "entry_time": now,
            "exit_price": None,
            "exit_option_price": None,
            "exit_time": None,
            "profit_loss": None,
            "profit_loss_percent": None,
            "pricing_mode": "UNDERLYING_ONLY",
            "status": "OPEN"
        }

        message = (
            "Paper 0DTE ATM option BUY executed (UNDERLYING_ONLY mode - "
            "Webull did not return an option price, likely the US_OPTION "
            "market-data permission limitation)"
        )

    save_trade(trade)

    return {
        "success": True,
        "message": message,
        "trade": trade,
        "option_market_data_response": option_result
    }


def paper_sell_spy():

    trade = get_open_trade()

    if not trade.get("open"):

        return {
            "success": False,
            "error": "No open paper trade"
        }

    contract = trade.get("contract")

    if not contract:

        return {
            "success": False,
            "error": "Open trade is missing its contract"
        }

    option_symbol = contract.get("symbol")

    current_spy_price = extract_spy_price()

    pricing_mode = trade.get("pricing_mode", "UNDERLYING_ONLY")

    if pricing_mode == "OPTION_PREMIUM" and option_symbol:

        option_result = get_option_price(option_symbol)
        option_exit_price = extract_option_price(option_result)

    else:

        option_result = None
        option_exit_price = None

    entry_option_price = trade.get("entry_option_price")

    if pricing_mode == "OPTION_PREMIUM" and entry_option_price is not None and option_exit_price is not None:

        multiplier = 100

        profit_loss = (option_exit_price - entry_option_price) * multiplier

        profit_loss_percent = (
            (option_exit_price - entry_option_price) / entry_option_price
        ) * 100

        trade["exit_option_price"] = option_exit_price
        trade["pricing_mode"] = "OPTION_PREMIUM"

        message = "Paper 0DTE ATM option SELL executed (OPTION_PREMIUM mode)"

    else:

        # Underlying-only fallback: same math as the original bot, using
        # percent move in SPY itself. Used either because the trade opened
        # in this mode, or because the option price became unavailable
        # between entry and exit.
        entry_price = trade.get("entry_price")

        if entry_price is None or current_spy_price is None:

            return {
                "success": False,
                "error": "Missing price data needed to close the trade",
                "trade": trade
            }

        profit_loss = ((current_spy_price - entry_price) / entry_price) * 100
        profit_loss_percent = profit_loss

        trade["exit_option_price"] = None
        trade["pricing_mode"] = "UNDERLYING_ONLY"

        message = "Paper 0DTE ATM option SELL executed (UNDERLYING_ONLY mode)"

    trade["open"] = False
    trade["exit_price"] = current_spy_price
    trade["exit_time"] = datetime.now(ET).isoformat()
    trade["profit_loss"] = round(profit_loss, 2)
    trade["profit_loss_percent"] = round(profit_loss_percent, 2)
    trade["status"] = "CLOSED"

    close_trade(trade)

    return {
        "success": True,
        "message": message,
        "trade": trade
    }


def paper_trade_status():

    open_trade = get_open_trade()

    if open_trade.get("open"):

        return {
            "success": True,
            "trade": open_trade
        }

    return {
        "success": True,
        "trade": get_latest_trade()
    }


def paper_trade_history():

    connection = get_db()

    try:

        rows = connection.execute(
            """
            SELECT *
            FROM paper_trades
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

        return {
            "success": True,
            "trades": [row_to_trade(row) for row in rows]
        }

    finally:

        connection.close()


def debug_option_chain():

    try:

        expiration_date = datetime.now(ET).strftime("%Y-%m-%d")

        contracts = get_option_contracts("CALL", expiration_date)

        if isinstance(contracts, dict) and "error" in contracts:

            return {
                "success": False,
                "error": contracts["error"]
            }

        return {
            "success": True,
            "expiration_date": expiration_date,
            "total_contracts": len(contracts),
            "sample_contracts": contracts[:10]
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def debug_0dte_selection():

    return select_0dte_atm_contract("CALL")


def debug_market_data():

    try:

        _, data_client = get_clients()

        return {
            "success": True,
            "instrument_methods": [
                x for x in dir(data_client.instrument)
                if not x.startswith("_")
            ]
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def test_options():

    return {
        "success": True,
        "message": (
            "0DTE ATM options system loaded. Falls back to UNDERLYING_ONLY "
            "pricing automatically until Webull enables US_OPTION "
            "market-data permission."
        )
    }
