import os
import inspect

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



def debug_option_method():

    try:

        _, data_client = get_clients()

        method = data_client.instrument.get_option_contracts

        return {

            "success": True,

            "signature": str(
                inspect.signature(method)
            ),

            "doc": str(
                inspect.getdoc(method)
            )

        }


    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def get_option_contracts(option_type="CALL"):

    try:

        _, data_client = get_clients()

        response = data_client.instrument.get_option_contracts(
            Category.US_OPTION.name,
            "SPY"
        )

        return response.json()

    except Exception as e:

        return {
            "error": str(e)
        }



def select_contract(option_type="CALL"):

    return {

        "success": False,

        "message": "Selector paused while inspecting SDK"

    }



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



def test_options():

    return {

        "success": True,

        "message": "Option test active"

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
