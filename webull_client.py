import os

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient


def get_api_client():

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

    return api_client



def test_webull_connection():

    try:

        api_client = get_api_client()

        trade_client = TradeClient(api_client)

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



def debug_sdk():

    try:

        import webull

        api_client = get_api_client()


        return {

            "success": True,

            "webull_modules": dir(webull),

            "api_client_methods": [
                x for x in dir(api_client)
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
        "message": "Waiting for contract endpoint"
    }



def select_contract(option_type="CALL"):

    return {
        "success": False,
        "error": "Contract lookup temporarily disabled while finding SDK endpoint"
    }



def paper_buy_spy():

    return {
        "success": True,
        "message": "Paper order placeholder"
    }



def debug_market_data():

    return debug_sdk()
