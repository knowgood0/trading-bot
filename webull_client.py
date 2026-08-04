import os

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient


def get_trade_client():

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

    return TradeClient(api_client), api_client



def test_webull_connection():

    try:

        trade_client, api_client = get_trade_client()

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

        trade_client, api_client = get_trade_client()

        result = trade_client.trade_instrument.get_trade_security_detail(
            "SPY",
            "US",
            "OPTION",
            "OPTION",
            "600",
            "2026-08-21"
        )

        return {
            "success": True,
            "response": result.json()
        }


    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }



def paper_buy_spy():

    return {
        "success": False,
        "message": "Disabled during option testing"
    }



def test_option_order():

    return {
        "success": False,
        "message": "Waiting for valid contract data"
    }
