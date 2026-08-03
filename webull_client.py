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
        "message": "Diagnostic mode"
    }


def test_options():
    return {
        "success": False,
        "message": "Diagnostic mode"
    }


def debug_trade_client():
    try:
        files = glob.glob(
            "/opt/render/project/src/.venv/lib/python3.14/site-packages/webull/**/*.py",
            recursive=True
        )

        option_files = []

        for file in files:
            try:
                with open(file, "r", errors="ignore") as f:
                    text = f.read().lower()

                    if "option" in text:
                        option_files.append(file)

            except:
                pass

        return {
            "success": True,
            "option_related_files": option_files[:50],
            "count": len(option_files)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
