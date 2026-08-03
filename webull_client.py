import os
import glob

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


def paper_buy_spy():
    return {
        "success": False,
        "message": "Disabled while building options"
    }


def test_options():
    return debug_option_models()


def debug_option_models():
    try:
        results = []

        files = glob.glob(
            "/opt/render/project/src/.venv/lib/python3.14/site-packages/webull/**/*.py",
            recursive=True
        )

        for file in files:
            if "option" in file.lower():

                try:
                    with open(file, "r", errors="ignore") as f:
                        text = f.read()

                    matches = []

                    for line in text.split("\n"):
                        if (
                            "strike" in line.lower()
                            or "expiration" in line.lower()
                            or "instrument_id" in line.lower()
                            or "symbol" in line.lower()
                        ):
                            matches.append(line.strip())

                    if matches:
                        results.append({
                            "file": file,
                            "matches": matches[:25]
                        })

                except:
                    pass

        return {
            "success": True,
            "results": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
