from flask import Flask, jsonify

from webull_client import (
    test_webull_connection,
    paper_buy_spy,
    test_options,
    debug_option_models
)


app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "status": "Trading bot is running"
    })


@app.route("/webull-test")
def webull_test():
    return jsonify(
        test_webull_connection()
    )


@app.route("/buy-test")
def buy_test():
    return jsonify(
        paper_buy_spy()
    )


@app.route("/options-test")
def options_test():
    return jsonify(
        test_options()
    )


@app.route("/option-models")
def option_models():
    return jsonify(
        debug_option_models()
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
