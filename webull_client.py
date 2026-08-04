import os
import uuid

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

from webull.data.request.get_option_contracts_request import GetOptionContractsRequest


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

        request = GetOptionContractsRequest()

        request.set_underlying_symbols("SPY")
        request.set_page_size(5)

        response = api_client.get_response(request)

        return {
            "success": True,
            "contracts": response.json()
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }



def paper_buy_spy():

    try:

        trade_client, api_client = get_trade_client()

        account_id = os.environ.get(
            "WEBULL_ACCOUNT_ID"
        )

        if not account_id:

            return {
                "success": False,
                "error": "Missing WEBULL_ACCOUNT_ID"
            }


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



def test_option_order():

    return {
        "success": False,
        "message": "Option order paused until real contract data is retrieved"
    }
