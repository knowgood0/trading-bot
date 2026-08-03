import os
import json
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient


def test_webull_connection():
    app_key = os.environ.get("WEBULL_APP_KEY")
    app_secret = os.environ.get("WEBULL_APP_SECRET")

    if not app_key or not app_secret:
        return {
            "success": False,
            "error": "Missing Webull API credentials"
        }

    try:
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

        response = trade_client.account_v2.get_account_list()

        if response.status_code == 200:
            return {
                "success": True,
                "account": response.json()
            }

        return {
            "success": False,
            "status": response.status_code,
            "error": response.text
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
