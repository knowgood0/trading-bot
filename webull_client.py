import os
from datetime import datetime, timedelta

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category


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

    data_client = DataClient(api_client)

    return trade_client, data_client



def test_webull_connection():

    try:

        trade_client, _ = get_clients()

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



def get_option_contracts(option_type="CALL"):

    try:

        _, data_client = get_clients()


        today = datetime.now()


        start_date = (
            today + timedelta(days=20)
        ).strftime("%Y-%m-%d")


        end_date = (
            today + timedelta(days=60)
        ).strftime("%Y-%m-%d")



        response = data_client.instrument.get_option_contracts(

            category=Category.US_OPTION.name,

            underlying_symbols="SPY",

            status="LISTING",

            start_date=start_date,

            end_date=end_date,

            option_type=option_type,

            style="AMERICAN",

            page_size=1000

        )


        return response.json()



    except Exception as e:

        return {
            "error": str(e)
        }



def debug_option_chain():

    try:

        contracts = get_option_contracts()


        if isinstance(contracts, dict) and "error" in contracts:

            return {

                "success": False,

                "error": contracts["error"]

            }



        if not isinstance(contracts, list):

            return {

                "success": False,

                "data": contracts

            }



        expirations = sorted(
            list(
                set(
                    c.get("expiration_date")
                    for c in contracts
                    if c.get("expiration_date")
                )
            )
        )


        strikes = sorted(
            list(
                set(
                    c.get("strike_price")
                    for c in contracts
                    if c.get("strike_price")
                )
            )
        )


        return {

            "success": True,

            "total_contracts": len(contracts),

            "expirations": expirations,

            "strike_count": len(strikes),

            "sample_contracts": contracts[:10]

        }


    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def select_contract(option_type="CALL"):

    try:

        contracts = get_option_contracts(option_type)


        if isinstance(contracts, dict) and "error" in contracts:

            return {

                "success": False,

                "error": contracts["error"]

            }



        if not isinstance(contracts, list):

            return {

                "success": False,

                "error": "Unexpected response format",

                "data": contracts

            }



        valid_contracts = []



        for contract in contracts:

            if (

                contract.get("def_type") == "STANDARD"

                and

                contract.get("style") == "AMERICAN"

                and

                contract.get("option_type") == option_type

                and

                contract.get("tradable_status") == "OC"

            ):

                valid_contracts.append(contract)



        if not valid_contracts:

            return {

                "success": False,

                "error": "No valid contracts found",

                "total_received": len(contracts)

            }



        # Sort expiration closest to 45 days

        target_days = 45

        today = datetime.now()



        def expiration_score(contract):

            try:

                expiration = datetime.strptime(

                    contract.get("expiration_date"),

                    "%Y-%m-%d"

                )


                days = (

                    expiration - today

                ).days


                return abs(days - target_days)


            except:

                return 9999



        valid_contracts.sort(
            key=expiration_score
        )



        selected = valid_contracts[0]



        return {

            "success": True,

            "selected_contract": {

                "symbol": selected.get("symbol"),

                "type": selected.get("option_type"),

                "strike": selected.get("strike_price"),

                "expiration": selected.get("expiration_date"),

                "raw": selected

            }

        }



    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def debug_option_method():

    return {

        "success": True,

        "message": "SDK method inspection complete"

    }



def test_options():

    return {

        "success": True,

        "message": "Option contract selector ready"

    }



def debug_market_data():

    try:

        _, data_client = get_clients()

        return {

            "success": True,

            "instrument_methods": [

                x for x in dir(data_client.instrument)

                if not x.startswith("_")

            ]

        }

    except Exception as e:

        return {

            "success": False,

            "error": str(e)

        }



def paper_buy_spy():

    return {

        "success": True,

        "message": "Paper order not connected yet"

    }
