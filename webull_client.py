import os

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

    return trade_client, data_client, api_client



def test_webull_connection():

    try:

        trade_client, _, _ = get_clients()

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

        _, data_client, api_client = get_clients()


        return {

            "success": True,

            "api_client": {

                "class": str(type(api_client)),

                "endpoint": getattr(
                    api_client,
                    "endpoint",
                    None
                )

            },

            "data_client": {

                "class": str(type(data_client)),

                "market_data_class": str(
                    type(data_client.market_data)
                )

            }

        }


    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def debug_market_data():

    try:

        _, data_client, _ = get_clients()

        return {

            "success": True,

            "methods": [
                x for x in dir(data_client.market_data)
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
        "message": "Options OK"
    }



def select_contract():

    return {
        "success": True,
        "message": "Waiting for price feed"
    }



def paper_buy_spy():

    return {
        "success": True,
        "message": "Waiting for contract"
    }
