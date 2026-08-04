from flask import Flask, jsonify, request

from webull_client import (
    test_webull_connection,
    test_options,
    select_contract,
    paper_buy_spy,
    debug_market_data
)


app = Flask(__name__)


@app.route("/")
def home():

    return jsonify({
        "status": "Trading bot running"
    })



@app.route("/webull-test")
def webull_test():

    return jsonify(
        test_webull_connection()
    )



@app.route("/options-test")
def options_test():

    return jsonify(
        test_options()
    )



@app.route("/select-contract")
def contract_test():

    return jsonify(
        select_contract("CALL")
    )



@app.route("/webhook", methods=["POST"])
def webhook():

    data = request.json


    option_type = data.get(
        "option_type",
        "CALL"
    )


    result = select_contract(
        option_type
    )


    return jsonify(result)



@app.route("/debug-market-data")
def market_debug():

    return jsonify(
        debug_market_data()
    )



@app.route("/buy-test")
def buy_test():

    return jsonify(
        paper_buy_spy()
    )



if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
    )
