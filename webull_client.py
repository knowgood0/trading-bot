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
            "success": True,
            "account": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def test_option_order():

    try:

        trade_client = get_trade_client()

        account_id = os.environ.get(
            "WEBULL_ACCOUNT_ID"
        )

        if not account_id:

            return {
                "success": False,
                "error": "Missing WEBULL_ACCOUNT_ID"
            }


        client_order_id = uuid.uuid4().hex


        option_order = [
            {
                "combo_type": "NORMAL",
                "client_order_id": client_order_id,
                "order_type": "MARKET",
                "quantity": "1",
                "side": "BUY",
                "time_in_force": "DAY",
                "entrust_type": "QTY",
                "legs": [
                    {
                        "symbol": "SPY260821C00600000",
                        "instrument_type": "OPTION",
                        "market": "US",
                        "side": "BUY",
                        "quantity": "1"
                    }
                ]
            }
        ]


        response = trade_client.order_v2.place_option(
            account_id,
            option_order
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
