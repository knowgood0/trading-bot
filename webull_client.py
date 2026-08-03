import os
import inspect

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

    return TradeClient(api_client)


def debug_trade_client():

    try:
        trade_client = get_trade_client()

        return {
            "success": True,

            "order_v2_methods": [
                x for x in dir(trade_client.order_v2)
                if not x.startswith("_")
            ],

            "order_v2_signatures": {
                x: str(inspect.signature(getattr(trade_client.order_v2, x)))
                for x in dir(trade_client.order_v2)
                if "option" in x.lower()
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def test_webull_connection():
    return {"success": True}


def paper_buy_spy():
    return {"success": False}


def test_options():
    return debug_trade_client()
