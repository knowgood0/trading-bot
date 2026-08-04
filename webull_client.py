import os

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

from webull.data.request.get_option_contracts_request import GetOptionContractsRequest


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

    trade_client = TradeClient(api_client)

    return trade_client, api_client



def test_webull_connection():

    try:

        trade_client, api_client = get_clients()

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



def find_contract():

    try:

        trade_client, api_client = get_clients()


        request = GetOptionContractsRequest()


        # Try the option chain query
        request.set_underlying_symbols("SPY")
        request.set_root_symbol("SPY")
        request.set_page_size(10)


        result = api_client.get_response(
            request
        )


        return {
            "success": True,
            "contracts": result.json()
        }


    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }



def test_options():

    return find_contract()



def paper_buy_spy():

    return {
        "success": False,
        "message": "Waiting for automatic contract selection"
    }



def test_option_order():

    return {
        "success": False,
        "message": "Waiting for contract selector"
    }
