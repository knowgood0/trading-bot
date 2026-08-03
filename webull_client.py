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


def test_webull_connection():
    try:
        trade_client = get_trade_client()

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


def paper_buy_spy():
    return {
        "success": False,
        "message": "Diagnostic mode"
    }


def test_options():
    return {
        "success": False,
        "message": "Diagnostic mode"
    }


def debug_trade_client():
    try:
        trade_client = get_trade_client()

        return {
            "success": True,

            "order_place_signature": str(
                inspect.signature(
                    trade_client.order_v3.place_order
                )
            ),

            "preview_signature": str(
                inspect.signature(
                    trade_client.order_v3.preview_order
                )
            ),

            "order_client_methods": [
                x for x in dir(trade_client.order_v3)
                if not x.startswith("_")
            ]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
