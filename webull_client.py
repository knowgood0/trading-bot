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

        if response.status_code == 200:
            return {
                "success": True,
                "account": response.json()
            }

        return {
            "success": False,
            "status": response.status_code,
            "error": response.text
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

        order_id = uuid.uuid4().hex

        order = [
            {
                "combo_type": "NORMAL",
                "client_order_id": order_id,
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

        # Try to retrieve SPY option chain
        response = trade_client.option.get_option_chain(
            "SPY"
        )

        return {
            "success": True,
            "options": response.json()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
