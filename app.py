import os
import importlib.metadata
import logging

from flask import Flask, request, jsonify

from webull_client import (
    test_webull_connection,
    account_diagnostic,
    resolve_account,
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
)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "status": "Trading bot online",
        "message": "Webull paper trading connected",
        "environment": "PAPER",
        "trading": "PAPER ONLY",
        "source_of_truth": "WEBULL_PAPER_ACCOUNT",
        "configured_account": resolve_account(),
    })


# ============================================================
# WEBULL SDK DIAGNOSTIC
# ============================================================

@app.route("/webull-sdk-info")
def webull_sdk_info():
    result = {
        "success": True,
        "package": "webull-openapi-python-sdk",
        "package_version": None,
        "webull_module": None,
        "webull_version": None,
        "python_version": None,
        "error": None,
    }

    try:
        result["package_version"] = importlib.metadata.version(
            "webull-openapi-python-sdk"
        )
    except Exception as e:
        result["error"] = f"Unable to read package version: {e}"

    try:
        import webull

        result["webull_module"] = getattr(webull, "__file__", None)
        result["webull_version"] = getattr(webull, "__version__", None)

    except Exception as e:
        result["success"] = False
        result["error"] = (
            result["error"] + "; " if result["error"] else ""
        ) + f"Unable to import webull module: {e}"

    try:
        import sys
        result["python_version"] = sys.version
    except Exception:
        pass

    return jsonify(result)


# ============================================================
# WEBULL TEST
# ============================================================

@app.route("/webull-test")
def webull_test():
    return jsonify(test_webull_connection())


# ============================================================
# SELECTED ACCOUNT
# ============================================================

@app.route("/selected-account")
def selected_account_test():
    return jsonify({
        "success": True,
        "environment": resolve_account().get("environment", "PAPER"),
        "account": resolve_account(),
    })


# ============================================================
# ACCOUNT DIAGNOSTIC
# ============================================================

@app.route("/account-diagnostic")
def account_diagnostic_test():
    return jsonify(account_diagnostic())


# ============================================================
# WEBULL POSITIONS
# ============================================================

@app.route("/webull-positions")
def webull_positions_test():
    return jsonify(get_webull_positions())


# ============================================================
# SPECIFIC OPTION POSITION
# ============================================================

@app.route("/webull-option-position")
def webull_option_position_test():
    symbol = request.args.get("symbol")

    if not symbol:
        return jsonify({
            "success": False,
            "error": "Missing option symbol",
        })

    return jsonify(get_webull_option_position(symbol))


# ============================================================
# CONTRACT TEST
# ============================================================

@app.route("/select-contract")
def select_contract_test():
    option_type = request.args.get("option_type", "CALL")
    return jsonify(select_contract(option_type))


# ============================================================
# SPY PRICE
# ============================================================

@app.route("/spy-price")
def spy_price_test():
    return jsonify(get_spy_price())


# ============================================================
# OPTION PRICE
# ============================================================

@app.route("/option-price")
def option_price_test():
    symbol = request.args.get("symbol")

    if not symbol:
        return jsonify({
            "success": False,
            "error": "Missing option symbol",
        })

    return jsonify(get_option_price(symbol))


# ============================================================
# DEBUG
# ============================================================

@app.route("/debug-option-chain")
def debug_option_chain_test():
    return jsonify(debug_option_chain())


@app.route("/debug-market-data")
def debug_market_test():
    return jsonify(debug_market_data())


@app.route("/options-test")
def options_test():
    return jsonify(test_options())


# ============================================================
# WEBULL PAPER BUY
# ============================================================

@app.route("/paper-buy")
def paper_buy_test():
    option_type = request.args.get("option_type", "CALL")
    return jsonify(paper_buy_spy(option_type))


# ============================================================
# WEBULL PAPER SELL
# ============================================================

@app.route("/paper-sell")
def paper_sell_test():
    return jsonify(paper_sell_spy())


# ============================================================
# PAPER STATUS
# ============================================================

@app.route("/paper-status")
def paper_status_test():
    return jsonify(paper_trade_status())


# ============================================================
# PAPER HISTORY
# ============================================================

@app.route("/paper-history")
def paper_history_test():
    try:
        trades = get_trade_history(50)

        return jsonify({
            "success": True,
            "count": len(trades),
            "trades": trades,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        })


# ============================================================
# ORDER DETAIL
# ============================================================

@app.route("/order-detail")
def order_detail_test():
    client_order_id = request.args.get("client_order_id")

    if not client_order_id:
        return jsonify({
            "success": False,
            "error": "Missing client_order_id",
        })

    return jsonify(test_order_detail(client_order_id))


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
            error="",
        )

        return jsonify({
            "success": True,
            "message": "Google Sheets test sent",
            "google_sheets": result,
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        })


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)

        app.logger.info("WEBHOOK RECEIVED")
        app.logger.info("Webhook payload: %s", data)

        if not data or not isinstance(data, dict):
            app.logger.error("No valid JSON payload received")
            return jsonify({
                "success": False,
                "error": "No valid JSON payload received",
            }), 400

        symbol = str(data.get("symbol", "SPY")).strip().upper()
        action = str(data.get("action", "")).strip().upper()
        option_type = str(data.get("option_type", "")).strip().upper()

        app.logger.info("Webhook parsed symbol=%s", symbol)
        app.logger.info("Webhook parsed action=%s", action)
        app.logger.info("Webhook parsed option_type=%s", option_type)

        if symbol != "SPY":
            return jsonify({
                "success": False,
                "error": f"Unsupported symbol: {symbol}. This bot trades SPY only.",
                "received_signal": {
                    "symbol": symbol,
                    "action": action,
                    "option_type": option_type,
                },
            }), 400

        if action not in ("BUY", "SELL"):
            return jsonify({
                "success": False,
                "error": f"Unknown action: {action}",
                "received_signal": {
                    "symbol": symbol,
                    "action": action,
                    "option_type": option_type,
                },
            }), 400

        if action == "BUY":
            if option_type not in ("CALL", "PUT"):
                return jsonify({
                    "success": False,
                    "error": (
                        "BUY webhook requires option_type "
                        "CALL or PUT"
                    ),
                    "received_signal": {
                        "symbol": symbol,
                        "action": action,
                        "option_type": option_type,
                    },
                }), 400

            app.logger.info(
                "WEBHOOK BUY -> paper_buy_spy(%s)",
                option_type,
            )

            # This is deliberately the exact same execution function used
            # by /paper-buy.
            trade_result = paper_buy_spy(option_type)

        else:
            app.logger.info(
                "WEBHOOK SELL -> paper_sell_spy()"
            )

            # SELL deliberately ignores the webhook option_type for contract
            # selection. The stored open trade is the source of truth.
            trade_result = paper_sell_spy()

        app.logger.info("Webhook final trade result: %s", trade_result)

        status_code = 200 if trade_result.get("success") else 400

        return jsonify({
            "success": trade_result.get("success", False),
            "received_signal": {
                "symbol": symbol,
                "action": action,
                "option_type": option_type,
            },
            "trade_result": trade_result,
        }), status_code

    except Exception as e:
        app.logger.exception("Webhook exception")

        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
    )
