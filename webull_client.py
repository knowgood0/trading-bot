import os
from datetime import datetime, timedelta

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient


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

            underlying_symbols="SPY",

            category="US_OPTION",

            status="LISTING",

            start_date=start_date,

            end_date=end_date,

            option_type=option_type,

            page_size=100

        )


        return response.json()



    except Exception as e:

        return {

            "error": str(e)

        }



def select_contract(option_type="CALL"):

    try:

        contracts = get_option_contracts(option_type)


        if "options" not in contracts:

            return {

                "success": False,

                "error": contracts

            }



        valid_contracts = []


        for contract in contracts["options"]:

            if (

                contract.get("def_type") == "STANDARD"

                and

                contract.get("style") == "AMERICAN"

                and

                contract.get("tradable_status") == "OC"

            ):

                valid_contracts.append(contract)



        if not valid_contracts:

            return {

                "success": False,

                "error": "No valid contracts found"

            }



        selected = valid_contracts[0]



        return {

            "success": True,

            "selected_contract": {

                "symbol": selected.get("symbol"),

                "type": selected.get("option_type"),

                "strike": selected.get("strike_price"),

                "expiration": selected.get("expiration_date")

            }

        }



    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def test_options():

    return {

        "success": True,

        "message": "Option contract selector ready"

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
