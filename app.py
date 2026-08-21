import os
import importlib.metadata
import logging

from flask import Flask, request, jsonify

from webull_client import (
    resolve_account,
    test_webull_connection,
    account_diagnostic,
    account_order_capability_test,
    inspect_order_api,
    get_webull_positions,
    get_webull_option_position,
    select_contract,
    get_spy_price,
    get_option_price,
    debug_option_chain,
    debug_market_data,
    test_options,
    paper_buy_spy,
    paper_sell_spy,
    paper_trade_status,
    get_trade_history,
    journal_trade,
    test_order_detail,
    reconcile_paper_state,
    test_google_sheets_connection,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def respond(result):
    code = int(result.get("http_status", 200)) if isinstance(result, dict) else 200
    if code < 100 or code > 599:
        code = 200
    return jsonify(result), code


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
        result["package_version"] = importlib.metadata.version("webull-openapi-python-sdk")
    except Exception as exc:
        result["error"] = f"Unable to read package version: {exc}"
    try:
        import webull
        result["webull_module"] = getattr(webull, "__file__", None)
        result["webull_version"] = getattr(webull, "__version__", None)
    except Exception as exc:
        result["success"] = False
        result["error"] = (result["error"] + "; " if result["error"] else "") + f"Unable to import webull module: {exc}"
    try:
        import sys
        result["python_version"] = sys.version
    except Exception:
        pass
    return jsonify(result)


@app.route("/webull-test")
def webull_test():
    return jsonify(test_webull_connection())


@app.route("/selected-account")
def selected_account():
    return jsonify({"success": True, "environment": resolve_account()["environment"], "account": resolve_account()})


@app.route("/account-diagnostic")
def account_diag():
    return jsonify(account_diagnostic())


@app.route("/order-capability-test")
def order_capability():
    return jsonify(account_order_capability_test())


@app.route("/order-api-inspect")
def order_api_inspect():
    return jsonify(inspect_order_api())


@app.route("/webull-positions")
def webull_positions():
    return jsonify(get_webull_positions())


@app.route("/webull-option-position")
def webull_option_position():
    symbol = request.args.get("symbol")
    option_type = request.args.get("option_type")
    strike = request.args.get("strike")
    expiration = request.args.get("expiration")
    if not symbol and not (option_type and strike and expiration):
        return jsonify({"success": False, "error": "Provide symbol or option_type+strike+expiration"}), 400
    try:
        strike_value = float(strike) if strike is not None else None
    except ValueError:
        return jsonify({"success": False, "error": "Invalid strike"}), 400
    return jsonify(get_webull_option_position(symbol, option_type, strike_value, expiration))


@app.route("/select-contract")
def select_contract_route():
    return jsonify(select_contract(request.args.get("option_type", "CALL")))


@app.route("/spy-price")
def spy_price():
    return jsonify(get_spy_price())


@app.route("/option-price")
def option_price():
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"success": False, "error": "Missing option symbol"}), 400
    return jsonify(get_option_price(symbol))


@app.route("/debug-option-chain")
def debug_chain():
    return jsonify(debug_option_chain())


@app.route("/debug-market-data")
def debug_market_data_route():
    return jsonify(debug_market_data())


@app.route("/options-test")
def options_test():
    return jsonify(test_options())


@app.route("/paper-buy")
def paper_buy():
    return respond(paper_buy_spy(request.args.get("option_type", "CALL")))


@app.route("/paper-sell")
def paper_sell():
    return respond(paper_sell_spy())


@app.route("/paper-status")
def paper_status():
    return jsonify(paper_trade_status())


@app.route("/paper-history")
def paper_history():
    trades = get_trade_history(50)
    return jsonify({"success": True, "count": len(trades), "trades": trades})


@app.route("/order-detail")
def order_detail():
    client_order_id = request.args.get("client_order_id")
    if not client_order_id:
        return jsonify({"success": False, "error": "Missing client_order_id"}), 400
    return jsonify(test_order_detail(client_order_id))


@app.route("/google-test")
def google_test():
    return jsonify(test_google_sheets_connection())


@app.route("/reconcile")
def reconcile():
    return jsonify(reconcile_paper_state())


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"success": False, "error": "No valid JSON payload received"}), 400

        symbol = str(data.get("symbol", "SPY")).upper().strip()
        action = str(data.get("action", "")).upper().strip()
        option_type = str(data.get("option_type", "")).upper().strip()

        if symbol != "SPY":
            return jsonify({"success": False, "error": f"Unsupported symbol: {symbol}"}), 400
        if action not in ("BUY", "SELL"):
            return jsonify({"success": False, "error": f"Unknown action: {action}"}), 400

        if action == "BUY":
            if option_type not in ("CALL", "PUT"):
                return jsonify({"success": False, "error": "BUY webhook requires option_type CALL or PUT"}), 400
            result = paper_buy_spy(option_type)
        else:
            result = paper_sell_spy()

        return respond({
            "success": result.get("success", False),
            "received_signal": {
                "symbol": symbol,
                "action": action,
                "option_type": option_type,
            },
            "trade_result": result,
        })

    except Exception as exc:
        logging.exception("Webhook exception")
        return jsonify({"success": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
