import os
from datetime import datetime, timedelta

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



def test_options():

    try:

        trade_client, api_client = get_clients()

        request = GetOptionContractsRequest()

        request.set_category(
            "US_OPTION"
        )

        request.set_underlying_symbols(
            "SPY"
        )

        request.set_status(
            "LISTING"
        )

        request.set_page_size(
            100
        )

        response = api_client.get_response(
            request
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



def select_contract():

    try:

        trade_client, api_client = get_clients()

        request = GetOptionContractsRequest()

        request.set_category(
            "US_OPTION"
        )

        request.set_underlying_symbols(
            "SPY"
        )

        request.set_status(
            "LISTING"
        )

        request.set_page_size(
            500
        )


        response = api_client.get_response(
            request
        )


        data = response.json()

        contracts = data.get(
            "options",
            []
        )


        if not contracts:

            return {
                "success": False,
                "error": "No contracts returned"
            }


        today = datetime.now()

        target_expiration = today + timedelta(
            days=45
        )


        candidates = []


        for c in contracts:

            # Remove weird contracts

            if c.get("def_type") != "STANDARD":
                continue


            if c.get("option_type") != "CALL":
                continue


            if c.get("style") != "AMERICAN":
                continue


            expiration = datetime.strptime(
                c["expiration_date"],
                "%Y-%m-%d"
            )


            days_difference = abs(
                (expiration - target_expiration).days
            )


            candidates.append(
                (
                    days_difference,
                    c
                )
            )


        if not candidates:

            return {
                "success": False,
                "error": "No matching contracts"
            }


        candidates.sort(
            key=lambda x: x[0]
        )


        selected = candidates[0][1]


        return {
            "success": True,
            "selected_contract": {
                "symbol": selected["symbol"],
                "expiration": selected["expiration_date"],
                "strike": selected["strike_price"],
                "type": selected["option_type"],
                "style": selected["style"]
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
        "message": "Paper trading disabled until contract selection is verified."
    }
