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

    trade_client = TradeClient(
        api_client
    )

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


        raw_data = response.json()


        # Webull SDK may return a list or dictionary

        if isinstance(raw_data, list):

            contracts = raw_data


        elif isinstance(raw_data, dict):

            contracts = raw_data.get(
                "options",
                []
            )


        else:

            contracts = []



        if not contracts:

            return {
                "success": False,
                "error": "No option contracts returned",
                "raw": raw_data
            }



        target_date = datetime.now() + timedelta(
            days=45
        )


        candidates = []



        for contract in contracts:


            if not isinstance(contract, dict):
                continue


            # Only normal US equity options

            if contract.get("def_type") != "STANDARD":
                continue


            if contract.get("option_type") != "CALL":
                continue


            if contract.get("style") != "AMERICAN":
                continue


            expiration_date = contract.get(
                "expiration_date"
            )


            if not expiration_date:
                continue



            try:

                expiration = datetime.strptime(
                    expiration_date,
                    "%Y-%m-%d"
                )

            except:

                continue



            distance = abs(
                (expiration - target_date).days
            )


            candidates.append(
                (
                    distance,
                    contract
                )
            )



        if not candidates:

            return {
                "success": False,
                "error": "No matching contracts found"
            }



        candidates.sort(
            key=lambda x: x[0]
        )


        selected = candidates[0][1]



        return {

            "success": True,

            "selected_contract": {

                "symbol": selected.get(
                    "symbol"
                ),

                "expiration": selected.get(
                    "expiration_date"
                ),

                "strike": selected.get(
                    "strike_price"
                ),

                "type": selected.get(
                    "option_type"
                ),

                "style": selected.get(
                    "style"
                ),

                "def_type": selected.get(
                    "def_type"
                )

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

        "message": "Paper trading order not enabled yet. Contract selection must pass first."

    }
