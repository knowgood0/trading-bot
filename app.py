from flask import Flask, request, jsonify
from datetime import datetime

from webull_client import test_webull_connection, paper_buy_spy

app = Flask(__name__)

# Simple test tracking
balance = 10000
position = None
trades = []


@app.route("/")
def home():
    return {
        "status": "Trading bot is running",
        "balance": balance,
        "open_position": position,
        "trades": trades
    }


@app.route("/webull-test")
def webull_test():
    return jsonify(test_webull_connection())


@app.route("/buy-test")
def buy_test():
    return jsonify(paper_buy_spy())


@app.route("/tradingview-webhook", methods=["POST"])
def tradingview_webhook():
    try:
        data = request.json

        action = data.get("action")

        if action == "BUY":
            result = paper_buy_spy()
            return jsonify(result)

        return jsonify({
            "success": False,
            "message": "No valid action received",
            "received": data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


# This simulates TradingView sending a BUY alert
@app.route("/tradingview-test")
def tradingview_test():
    fake_signal = {
        "action": "BUY"
    }

    if fake_signal["action"] == "BUY":
        result = paper_buy_spy()
        return jsonify({
            "test": "TradingView simulation",
            "signal": fake_signal,
            "result": result
        })

    return jsonify({
        "success": False,
        "message": "No signal"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
