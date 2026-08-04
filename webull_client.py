import os
from datetime import datetime, timedelta

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


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

            quote = data[0]

            if "price" in quote:

                return float(
                    quote["price"]
                )

            if "close" in quote:

                return float(
                    quote["close"]
                )


        if isinstance(data, dict):

            if "price" in data:

                return float(
                    data["price"]
                )


    except Exception:

        pass


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


        valid_contracts = []


        for contract in contracts:

            if (

                contract.get("def_type") == "STANDARD"

                and

                contract.get("style") == "AMERICAN"

                and

                contract.get("option_type") == option_type

                and

                contract.get("tradable_status") == "OC"

            ):

                valid_contracts.append(contract)



        if not valid_contracts:

            return {

                "success": False,

                "error": "No valid contracts found"

            }



        if spy_price:


            valid_contracts.sort(

                key=lambda x:

                abs(

                    float(x.get("strike_price"))

                    -

                    spy_price

                )

            )


        else:

            valid_contracts.sort(

                key=lambda x:

                float(x.get("strike_price"))

            )



        selected = valid_contracts[0]


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



def paper_buy_spy():

    return {

        "success": True,

        "message": "Paper order not connected yet"

    }
