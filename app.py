from flask import Flask, request, jsonify
from datetime import datetime

from webull_client import test_webull_connection, paper_buy_spy

app = Flask(__name__)

# Bot state
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


@app.route("/tradingview-webhook", methods=["POST"])
def tradingview_webhook():
    global position

    try:
        data = request.json

        action = data.get("action")
        ticker = data.get("ticker", "SPY")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # BUY signal
        if action == "BUY":

            if position is not None:
                return jsonify({
                    "success": False,
                    "message": "Already holding position",
                    "position": position
                })

            result = paper_buy_spy()

            if result.get("success"):
                position = {
                    "ticker": ticker,
                    "entry_time": timestamp
                }

                trades.append({
                    "action": "BUY",
                    "ticker": ticker,
                    "time": timestamp,
                    "result": result
                })

            return jsonify(result)


        # SELL signal placeholder
        elif action == "SELL":

            if position is None:
                return jsonify({
                    "success": False,
                    "message": "No open position to sell"
                })

            trades.append({
                "action": "SELL",
                "ticker": ticker,
                "time": timestamp
            })

            position = None

            return jsonify({
                "success": True,
                "message": "Sell recorded"
            })


        return jsonify({
            "success": False,
            "message": "Unknown action",
            "received": data
        })


    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


# Simulates TradingView
@app.route("/tradingview-test")
def tradingview_test():

    fake_signal = {
        "action": "BUY",
        "ticker": "SPY"
    }

    result = paper_buy_spy()

    return jsonify({
        "test": "TradingView simulation",
        "signal": fake_signal,
        "result": result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
