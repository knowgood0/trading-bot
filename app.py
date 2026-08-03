from flask import Flask, jsonify

from webull_client import (
    test_webull_connection,
    test_options,
    paper_buy_spy,
    debug_place_option_request
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


@app.route("/buy-test")
def buy_test():

    return jsonify(
        paper_buy_spy()
    )


@app.route("/debug-option-order")
def debug_option_order():

    return jsonify(
        debug_place_option_request()
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=10000
    )
