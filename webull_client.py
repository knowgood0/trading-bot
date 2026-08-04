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
        request.set_root_symbol("SPY")
        request.set_page_size(10)
        request.set_status("ACTIVE")

        return {
            "success": True,
            "request": {
                "endpoint": request.get_endpoint(),
                "version": request.get_version(),
                "query": request.get_query_params()
            }
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }



def paper_buy_spy():

    return {
        "success": False,
        "message": "Stock order test paused"
    }



def test_option_order():

    return {
        "success": False,
        "message": "Waiting for real option contract data"
    }
