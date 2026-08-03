import os
import glob

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient


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

    return (
        TradeClient(api_client),
        DataClient(api_client)
    )


def test_webull_connection():

    try:
        trade_client, data_client = get_clients()

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


def find_option_examples():

    try:

        matches = []

        files = glob.glob(
            "/opt/render/project/src/.venv/lib/python3.14/site-packages/webull/**/*.py",
            recursive=True
        )

        for file in files:

            if "option" in file.lower():

                with open(file, "r", errors="ignore") as f:
                    text = f.read()

                for line in text.split("\n"):

                    if (
                        "new_orders" in line
                        or "legs" in line
                        or "option_symbol" in line
                        or "instrument_type" in line
                    ):
                        matches.append({
                            "file": file.split("/")[-1],
                            "line": line.strip()
                        })

        return {
            "success": True,
            "matches": matches[:100]
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


def paper_buy_spy():

    return {
        "success": False,
        "message": "Waiting for option order setup"
    }


def test_options():

    return find_option_examples()
