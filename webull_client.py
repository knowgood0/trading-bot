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
        "message": "Disabled during option debugging"
    }


def test_options():
    try:
        files = glob.glob(
            "/opt/render/project/src/.venv/lib/python3.14/site-packages/webull/**/*.py",
            recursive=True
        )

        results = []

        for file in files:
            if (
                "place_option_request.py" in file
                or "order_operation_v2.py" in file
            ):
                with open(file, "r", errors="ignore") as f:
                    results.append({
                        "file": file,
                        "content": f.read()[:8000]
                    })

        return {
            "success": True,
            "files": results
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
