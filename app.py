from flask import Flask, request, jsonify
from datetime import datetime
from webull_client import test_webull_connection, paper_buy_spy

app = Flask(__name__)

# Paper trading account
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


@app.route("/webhook", methods=["POST"])
def webhook():
    global balance, position

    data = request.json

    action = data.get("action")
    ticker = data.get("ticker", "SPY")
    price = float(data.get("price", 0))

    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "BUY" and position is None:
        position = {
            "ticker": ticker,
            "entry": price,
            "time": time
        }

        trades.append({
            "type": "BUY",
            "price": price,
            "time": time
        })

    elif action == "SELL" and position is not None:
        profit = price - position["entry"]

        balance += profit * 100

        trades.append({
            "type": "SELL",
            "entry": position["entry"],
            "exit": price,
            "profit": profit * 100,
            "time": time
        })

        position = None

    return jsonify({
        "received": True,
        "position": position,
        "balance": balance
    })


@app.route("/webull-test")
def webull_test():
    return jsonify(test_webull_connection())
    
@app.route("/buy-test")
def buy_test():
    return jsonify(paper_buy_spy())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
