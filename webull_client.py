import os

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

        attempts = []


        tests = [
            {
                "underlying_symbols": "SPY",
                "page_size": 5
            },
            {
                "root_symbol": "SPY",
                "page_size": 5
            },
            {
                "option_symbol": "SPY",
                "page_size": 5
            }
        ]


        for params in tests:

            request = GetOptionContractsRequest()

            if "underlying_symbols" in params:
                request.set_underlying_symbols(
                    params["underlying_symbols"]
                )

            if "root_symbol" in params:
                request.set_root_symbol(
                    params["root_symbol"]
                )

            if "option_symbol" in params:
                request.set_option_symbol(
                    params["option_symbol"]
                )

            request.set_page_size(
                params["page_size"]
            )


            try:

                response = api_client.get_response(
                    request
                )

                attempts.append({
                    "params": params,
                    "success": True,
                    "response": response.json()
                })


            except Exception as e:

                attempts.append({
                    "params": params,
                    "success": False,
                    "error": str(e)
                })


        return {
            "success": True,
            "attempts": attempts
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
        "message": "Waiting for valid contract"
    }
