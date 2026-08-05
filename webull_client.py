import os
from datetime import datetime, timedelta

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


paper_trade = {
    "open": False,
    "contract": None,
    "entry_price": None,
    "entry_time": None,
    "exit_price": None,
    "profit_loss": None
}


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

        today = datetime.now()

        start_date = (
            today + timedelta(days=20)
        ).strftime("%Y-%m-%d")

        end_date = (
            today + timedelta(days=60)
        ).strftime("%Y-%m-%d")


        response = data_client.instrument.get_option_contracts(

            category=Category.US_OPTION.name,

            underlying_symbols="SPY",

            status="LISTING",

            start_date=start_date,

            end_date=end_date,

            option_type=option_type,

            style="AMERICAN",

            page_size=1000

        )

        return response.json()


    except Exception as e:

        return {
            "error": str(e)
        }


def select_contract(option_type="CALL"):

    try:

        contracts = get_option_contracts(option_type)

        if isinstance(contracts, dict) and "error" in contracts:

            return {
                "success": False,
                "error": contracts["error"]
            }


        spy_price = extract_spy_price()

        valid = []


        for contract in contracts:

            if (
                contract.get("def_type") == "STANDARD"
                and contract.get("style") == "AMERICAN"
                and contract.get("tradable_status") == "OC"
                and contract.get("option_type") == option_type
            ):

                valid.append(contract)


        if not valid:

            return {
                "success": False,
                "error": "No valid contracts found"
            }


        if spy_price:

            valid.sort(
                key=lambda x:
                abs(
                    float(x["strike_price"]) - spy_price
                )
            )


        selected = valid[0]


        return {

            "success": True,

            "spy_price": spy_price,

            "selected_contract": {

                "symbol": selected.get("symbol"),

                "type": selected.get("option_type"),

                "strike": selected.get("strike_price"),

                "expiration": selected.get("expiration_date"),

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
        
def debug_option_chain():

    try:

        contracts = get_option_contracts()

        return {

            "success": True,

            "total_contracts": len(contracts),

            "sample_contracts": contracts[:10]

        }


    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



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



def paper_buy_spy(option_type="CALL"):

    global paper_trade


    if paper_trade["open"]:

        return {

            "success": False,

            "error": "A paper trade is already open",

            "trade": paper_trade

        }



    contract_result = select_contract(option_type)


    if not contract_result.get("success"):

        return contract_result



    spy_price = contract_result.get("spy_price")


    paper_trade = {

        "open": True,

        "contract": contract_result["selected_contract"],

        "entry_price": spy_price,

        "entry_time": datetime.now().isoformat(),

        "exit_price": None,

        "profit_loss": None

    }


    return {

        "success": True,

        "message": "Paper BUY executed",

        "trade": paper_trade

    }



def paper_sell_spy():

    global paper_trade


    if not paper_trade["open"]:

        return {

            "success": False,

            "error": "No open paper trade"

        }



    current_price = extract_spy_price()


    if current_price is None:

        return {

            "success": False,

            "error": "Unable to get current SPY price"

        }



    entry = paper_trade["entry_price"]


    if entry is None:

        return {

            "success": False,

            "error": "Missing entry price"

        }



    profit_loss = (

        (current_price - entry)

        /

        entry

    ) * 100



    paper_trade["exit_price"] = current_price

    paper_trade["profit_loss"] = round(
        profit_loss,
        2
    )

    paper_trade["open"] = False



    return {

        "success": True,

        "message": "Paper SELL executed",

        "trade": paper_trade

    }



def paper_trade_status():

    return {

        "success": True,

        "trade": paper_trade

    }



def test_options():

    return {

        "success": True,

        "message": "Options system online"

    }
