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


def debug_everything():

    try:
        trade_client = get_trade_client()

        return {
            "success": True,

            "trade_client_modules": [
                x for x in dir(trade_client)
                if not x.startswith("_")
            ],

            "order_methods": [
                x for x in dir(trade_client.order_v3)
                if not x.startswith("_")
            ],

            "instrument_methods": [
                x for x in dir(trade_client.trade_instrument)
                if not x.startswith("_")
            ],

            "instrument_signatures": {
                "detail": str(
                    inspect.signature(
                        trade_client.trade_instrument.get_trade_instrument_detail
                    )
                ),
                "security": str(
                    inspect.signature(
                        trade_client.trade_instrument.get_trade_security_detail
                    )
                ),
                "tradable": str(
                    inspect.signature(
                        trade_client.trade_instrument.get_tradeable_instruments
                    )
                )
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


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
