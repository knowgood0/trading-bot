from flask import Flask, request, jsonify

from webull_client import (
    test_webull_connection,
    account_diagnostic,
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
    test_options,
    get_webull_positions,
    get_webull_option_position,
    test_order_detail,
    resolve_account
)


app = Flask(__name__)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return jsonify({

        "status":
            "Trading bot online",

        "message":
            "Webull SANDBOX paper trading connected",

        "environment":
            "SANDBOX",

        "trading":
            "PAPER ONLY",

        "source_of_truth":
            "WEBULL_SANDBOX"

    })


# ============================================================
# WEBULL TEST
# ============================================================

@app.route("/webull-test")
def webull_test():

    return jsonify(
        test_webull_connection()
    )


# ============================================================
# SELECTED ACCOUNT
# ============================================================

@app.route("/selected-account")
def selected_account_test():

    try:

        account = resolve_account()

        return jsonify({

            "success": True,

            "environment":
                "SANDBOX",

            "account":
                account

        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        })


# ============================================================
# ACCOUNT DIAGNOSTIC
# ============================================================

@app.route("/account-diagnostic")
def account_diagnostic_test():

    return jsonify(
        account_diagnostic()
    )


# ============================================================
# WEBULL POSITIONS
# ============================================================

@app.route("/webull-positions")
def webull_positions_test():

    return jsonify(
        get_webull_positions()
    )


# ============================================================
# SPECIFIC OPTION POSITION
# ============================================================

@app.route("/webull-option-position")
def webull_option_position_test():

    symbol = request.args.get(
        "symbol"
    )

    if not symbol:

        return jsonify({

            "success": False,

            "error":
                "Missing option symbol"

        })

    return jsonify(
        get_webull_option_position(
            symbol
        )
    )


# ============================================================
# CONTRACT TEST
# ============================================================

@app.route("/select-contract")
def select_contract_test():

    option_type = request.args.get(
        "option_type",
        "CALL"
    )

    return jsonify(
        select_contract(option_type)
    )


# ============================================================
# SPY PRICE
# ============================================================

@app.route("/spy-price")
def spy_price_test():

    return jsonify(
        get_spy_price()
    )


# ============================================================
# OPTION PRICE
# ============================================================

@app.route("/option-price")
def option_price_test():

    symbol = request.args.get(
        "symbol"
    )

    if not symbol:

        return jsonify({

            "success": False,

            "error":
                "Missing option symbol"

        })

    return jsonify(
        get_option_price(symbol)
    )


# ============================================================
# DEBUG
# ============================================================

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


# ============================================================
# ACTUAL WEBULL SANDBOX PAPER BUY
# ============================================================

@app.route("/paper-buy")
def paper_buy_test():

    option_type = request.args.get(
        "option_type",
        "CALL"
    )

    return jsonify(
        paper_buy_spy(option_type)
    )


# ============================================================
# ACTUAL WEBULL SANDBOX PAPER SELL
# ============================================================

@app.route("/paper-sell")
def paper_sell_test():

    return jsonify(
        paper_sell_spy()
    )


# ============================================================
# PAPER STATUS
# ============================================================

@app.route("/paper-status")
def paper_status_test():

    return jsonify(
        paper_trade_status()
    )


# ============================================================
# PAPER HISTORY
# ============================================================

@app.route("/paper-history")
def paper_history_test():

    try:

        trades = get_trade_history(50)

        return jsonify({

            "success": True,

            "count":
                len(trades),

            "trades":
                trades

        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)

        })


# ============================================================
# ORDER DETAIL
# ============================================================

@app.route("/order-detail")
def order_detail_test():

    client_order_id = request.args.get(
        "client_order_id"
    )

    if not client_order_id:

        return jsonify({

            "success": False,

            "error":
                "Missing client_order_id"

        })

    return jsonify(
        test_order_detail(
            client_order_id
        )
    )


# ============================================================
# GOOGLE TEST
# ============================================================

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

            "error":
                str(e)

        })


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def webhook():

    try:

        data = request.json

        app.logger.info(
            f"Webhook received: {data}"
        )

        if not data:

            app.logger.error(
                "No JSON payload received"
            )

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
        # ACTUAL WEBULL SANDBOX BUY
        # ----------------------------------------------------

        if action == "BUY":

            trade_result = paper_buy_spy(
                option_type
            )


        # ----------------------------------------------------
        # ACTUAL WEBULL SANDBOX SELL
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


        # The webhook itself was received successfully.
        # trade_result.success tells us whether Webull
        # actually accepted the requested operation.

        return jsonify({

            "success": True,

            "received_signal": {

                "symbol":
                    symbol,

                "action":
                    action,

                "option_type":
                    option_type

            },

            "trade_result":
                trade_result

        })


    except Exception as e:

        app.logger.exception(
            "Webhook exception"
        )

        return jsonify({

            "success": False,

            "error":
                str(e)

        })


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000

        )
