from flask import Flask, request, jsonify

from webull_client import (
    test_webull_connection,
    select_contract,
    get_spy_price,
    get_option_price,
    debug_option_chain,
    debug_market_data,
    paper_buy_spy,
    paper_sell_spy,
    paper_trade_status,
    get_trade_history,
    journal_trade,
    test_options
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
def debug_market_test():

    return jsonify(
        debug_market_data()
    )


@app.route("/options-test")
def options_test():

    return jsonify(
        test_options()
    )


@app.route("/paper-buy")
def paper_buy_test():

    option_type = request.args.get(
        "option_type",
        "CALL"
    )

    return jsonify(
        paper_buy_spy(option_type)
    )


@app.route("/paper-sell")
def paper_sell_test():

    return jsonify(
        paper_sell_spy()
    )


@app.route("/paper-status")
def paper_status_test():

    return jsonify(
        paper_trade_status()
    )


@app.route("/paper-history")
def paper_history_test():

    try:

        trades = get_trade_history(50)

        return jsonify({
            "success": True,
            "count": len(trades),
            "trades": trades
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route("/google-test")
def google_test():

    try:

        result = journal_trade(
            event="GOOGLE_TEST",
            action="TEST",
            symbol="SPY",
            option_type="CALL",
            contract="TEST-CONTRACT",
            expiration="TEST",
            strike=0,
            spy_price=0,
            option_premium=0,
            entry_price=0,
            exit_price=0,
            profit_loss=0,
            pricing_mode="TEST",
            result="SUCCESS",
            error=""
        )

        return jsonify({
            "success": True,
            "message":
                "Google Sheets test sent",
            "google_sheets":
                result
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    try:

        data = request.get_json(
            silent=True
        )

        app.logger.info(
            f"Webhook received: {data}"
        )

        if not data:

            return jsonify({
                "success": False,
                "error":
                    "No JSON payload received"
            })

        symbol = data.get(
            "symbol",
            "SPY"
        )

        action = str(
            data.get(
                "action",
                "BUY"
            )
        ).upper()

        option_type = str(
            data.get(
                "option_type",
                "CALL"
            )
        ).upper()

        # ----------------------------------------------------
        # BUY
        # ----------------------------------------------------

        if action == "BUY":

            trade_result = paper_buy_spy(
                option_type
            )

        # ----------------------------------------------------
        # SELL
        # ----------------------------------------------------

        elif action == "SELL":

            trade_result = paper_sell_spy()

        else:

            trade_result = {
                "success": False,
                "error":
                    "Unknown action: "
                    + action
            }

        app.logger.info(
            f"Trade result: {trade_result}"
        )

        return jsonify({
            "success": True,
            "received_signal": {
                "symbol": symbol,
                "action": action,
                "option_type": option_type
            },
            "trade_result": trade_result
        })

    except Exception as e:

        app.logger.exception(
            "Webhook exception"
        )

        return jsonify({
            "success": False,
            "error": str(e)
        })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
