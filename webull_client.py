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

    return (
        TradeClient(api_client),
        DataClient(api_client)
    )



def test_webull_connection():

    try:

        trade_client, data_client = get_clients()

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

    try:

        trade_client, data_client = get_clients()

        option_symbol = "SPY260821C00600000"

        response = data_client.option_market_data.get_option_snapshot(
            option_symbol,
            "US_OPTION"
        )

        return {
            "success": True,
            "snapshot": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }



def paper_buy_spy():

    return {
        "success": False,
        "message": "Disabled"
    }



def test_option_order():

    return {
        "success": False,
        "message": "Waiting for verified option symbol"
    }
