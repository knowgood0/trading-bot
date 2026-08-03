from flask import Flask, request, jsonify
from datetime import datetime

from webull_client import (
    test_webull_connection,
    paper_buy_spy,
    test_options,
    debug_trade_client
)

app = Flask(__name__)

position = None
trades = []


@app.route("/")
def home():
    return jsonify({
        "status": "Trading bot is running",
        "position": position,
        "trades": trades
    })


@app.route("/webull-test")
def webull_test():
    return jsonify(test_webull_connection())


@app.route("/buy-test")
def buy_test():
    return jsonify(paper_buy_spy())


@app.route("/options-test")
def options_test():
    return jsonify(test_options())


@app.route("/debug")
def debug():
    return jsonify(debug_trade_client())


@app.route("/tradingview-webhook", methods=["POST"])
def tradingview_webhook():
    global position

    try:
        data = request.json

        action = data.get("action")
        ticker = data.get("ticker", "SPY")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "BUY":

            if position is not None:
                return jsonify({
                    "success": False,
                    "message": "Already holding position"
                })

            result = paper_buy_spy()

            if result.get("success"):
                position = {
                    "ticker": ticker,
                    "time": timestamp
                }

                trades.append({
                    "action": "BUY",
                    "ticker": ticker,
                    "time": timestamp
                })

            return jsonify(result)


        elif action == "SELL":

            position = None

            trades.append({
                "action": "SELL",
                "ticker": ticker,
                "time": timestamp
            })

            return jsonify({
                "success": True,
                "message": "Sell recorded"
            })


        return jsonify({
            "success": False,
            "message": "Unknown action"
        })


    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/tradingview-test")
def tradingview_test():

    result = paper_buy_spy()

    return jsonify({
        "test": "TradingView simulation",
        "signal": {
            "action": "BUY",
            "ticker": "SPY"
        },
        "result": result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
