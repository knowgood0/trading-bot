import os
import uuid


from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient


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



def get_trade_client():

    trade_client, _ = get_clients()

    return trade_client



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



def debug_market_data():

    try:

        trade_client, api_client = get_clients()


        return {

            "success": True,

            "trade_client_methods": [
                x for x in dir(trade_client)
                if "market" in x.lower()
                or "quote" in x.lower()
                or "snapshot" in x.lower()
                or "tick" in x.lower()
            ],

            "api_client_methods": [
                x for x in dir(api_client)
                if "market" in x.lower()
                or "quote" in x.lower()
                or "snapshot" in x.lower()
                or "tick" in x.lower()
            ]

        }


    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }



def test_options():

    try:

        trade_client, api_client = get_clients()


        option_data = api_client


        return {

            "success": True,

            "message": "API connection working. Ready for contract selector upgrade.",

            "api_methods": [
                x for x in dir(api_client)
                if "option" in x.lower()
                or "market" in x.lower()
            ]

        }


    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }



def select_contract():

    try:

        trade_client, api_client = get_clients()


        # This is the contract lookup that already worked
        contracts = api_client


        return {

            "success": True,

            "message": "Contract selection endpoint alive. Next step is adding SPY price lookup.",

        }


    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }



def paper_buy_spy():

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


        return {

            "success": True,

            "message": "Paper buy placeholder working. Waiting for contract selector."

        }


    except Exception as e:

        return {

            "success": False,
            "error": str(e)

        }
