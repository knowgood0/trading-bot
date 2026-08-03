import os
import uuid

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
            "success": response.status_code == 200,
            "account": response.json()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def paper_buy_spy():
    try:
        trade_client = get_trade_client()

        account_id = os.environ.get("WEBULL_ACCOUNT_ID")

        order = [
            {
                "combo_type": "NORMAL",
                "client_order_id": uuid.uuid4().hex,
                "symbol": "SPY",
                "instrument_type": "EQUITY",
                "market": "US",
                "order_type": "MARKET",
                "quantity": "1",
                "side": "BUY",
                "time_in_force": "DAY",
                "entrust_type": "QTY"
            }
        ]

        response = trade_client.order_v3.place_order(
            account_id,
            order
        )

        return {
            "success": True,
            "response": response.json()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def test_options():

    try:
        trade_client = get_trade_client()

        # Example: SPY option lookup
        response = trade_client.trade_instrument.get_trade_security_detail(
            "SPY",
            "US",
            "OPTION",
            "OPTION",
            "600",
            "2026-08-03"
        )

        return {
            "success": True,
            "option_data": response.json()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def debug_trade_client():
    return test_options()
