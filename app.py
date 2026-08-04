from flask import Flask, request, jsonify

from webull_client import (
    test_webull_connection,
    select_contract,
    debug_market_data,
    debug_option_chain,
    get_spy_price,
    get_option_price,
    paper_buy_spy
)


app = Flask(__name__)


@app.route("/")
def home():

    return jsonify({
        "status": "Trading bot online",
        "message": "Webull sandbox connected"
    })


@app.route("/webull-test")
def webull_test():

    return jsonify(
        test_webull_connection()
    )


@app.route("/select-contract")
def select_contract_test():

    option_type = request.args.get(
        "option_type",
        "CALL"
    )

    return jsonify(
        select_contract(option_type)
    )


@app.route("/spy-price")
def spy_price_test():

    return jsonify(
        get_spy_price()
    )


@app.route("/option-price")
def option_price_test():

    symbol = request.args.get(
        "symbol"
    )

    if not symbol:

        return jsonify({
            "success": False,
            "error": "Missing option symbol"
        })


    return jsonify(
        get_option_price(symbol)
    )


@app.route("/debug-option-chain")
def debug_option_chain_test():

    return jsonify(
        debug_option_chain()
    )


@app.route("/debug-market-data")
def debug_market():

    return jsonify(
        debug_market_data()
    )


@app.route("/buy-test")
def buy_test():

    return jsonify(
        paper_buy_spy()
    )


@app.route("/webhook", methods=["POST"])
def webhook():

    try:

        data = request.json


        if not data:

            return jsonify({
                "success": False,
                "error": "No JSON payload received"
            })


        symbol = data.get(
            "symbol",
            "SPY"
        )

        action = data.get(
            "action",
            "BUY"
        )

        option_type = data.get(
            "option_type",
            "CALL"
        )


        contract = select_contract(
            option_type
        )


        return jsonify({

            "success": True,

            "received_signal": {

                "symbol": symbol,

                "action": action,

                "option_type": option_type

            },

            "contract_selection": contract

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
