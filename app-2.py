import os,importlib.metadata,logging
from flask import Flask,request,jsonify
from webull_client import *
app=Flask(__name__);logging.basicConfig(level=logging.INFO)

def j(x,code=200):return jsonify(x),code
@app.route('/')
def home():return jsonify({'status':'Trading bot online','message':'Webull paper trading connected','environment':'PAPER','trading':'PAPER ONLY','source_of_truth':'WEBULL_PAPER_ACCOUNT','configured_account':resolve_account()})
@app.route('/webull-sdk-info')
def sdk():
 r={'success':True,'package':'webull-openapi-python-sdk','package_version':None,'python_version':None,'error':None}
 try:r['package_version']=importlib.metadata.version('webull-openapi-python-sdk')
 except Exception as e:r['error']=str(e)
 try:import sys;r['python_version']=sys.version
 except:pass
 return jsonify(r)
@app.route('/webull-test')
def wt():return jsonify(test_webull_connection())
@app.route('/selected-account')
def sa():return jsonify({'success':True,'account':resolve_account()})
@app.route('/account-diagnostic')
def ad():return jsonify(account_diagnostic())
@app.route('/order-capability-test')
def oct():return jsonify(account_order_capability_test())
@app.route('/order-api-inspect')
def oai():return jsonify(inspect_order_api())
@app.route('/webull-positions')
def wp():return jsonify(get_webull_positions())
@app.route('/webull-option-position')
def wop():
 s=request.args.get('symbol');return j({'success':False,'error':'Missing option symbol'},400) if not s else jsonify(get_webull_option_position(s))
@app.route('/select-contract')
def sc():return jsonify(select_contract(request.args.get('option_type','CALL')))
@app.route('/spy-price')
def sp():return jsonify(get_spy_price())
@app.route('/option-price')
def op():
 s=request.args.get('symbol');return j({'success':False,'error':'Missing option symbol'},400) if not s else jsonify(get_option_price(s))
@app.route('/debug-option-chain')
def doc():return jsonify(debug_option_chain())
@app.route('/debug-market-data')
def dmd():return jsonify(debug_market_data())
@app.route('/options-test')
def ot():return jsonify(test_options())
@app.route('/paper-buy')
def pb():return jsonify(paper_buy_spy(request.args.get('option_type','CALL')))
@app.route('/paper-sell')
def ps():return jsonify(paper_sell_spy())
@app.route('/paper-status')
def pts():return jsonify(paper_trade_status())
@app.route('/paper-history')
def ph():return jsonify({'success':True,'count':len(get_trade_history(50)),'trades':get_trade_history(50)})
@app.route('/order-detail')
def od():
 o=request.args.get('client_order_id');return j({'success':False,'error':'Missing client_order_id'},400) if not o else jsonify(test_order_detail(o))
@app.route('/google-test')
def gt():return jsonify(journal_trade('GOOGLE_TEST','TEST',option_type='CALL',contract='TEST-CONTRACT',expiration='TEST',strike=0,spy_price=0,option_premium=0,entry_price=0,exit_price=0,profit_loss=0,pricing_mode='TEST',result='SUCCESS'))
@app.route('/webhook',methods=['POST'])
def webhook():
 try:
  d=request.get_json(silent=True)
  if not isinstance(d,dict):return j({'success':False,'error':'No valid JSON payload received'},400)
  sym=str(d.get('symbol','SPY')).upper().strip();act=str(d.get('action','')).upper().strip();typ=str(d.get('option_type','')).upper().strip()
  if sym!='SPY':return j({'success':False,'error':f'Unsupported symbol: {sym}'},400)
  if act not in ('BUY','SELL'):return j({'success':False,'error':f'Unknown action: {act}'},400)
  if act=='BUY':
   if typ not in ('CALL','PUT'):return j({'success':False,'error':'BUY webhook requires option_type CALL or PUT'},400)
   result=paper_buy_spy(typ)
  else:result=paper_sell_spy()
  return j({'success':result.get('success',False),'received_signal':{'symbol':sym,'action':act,'option_type':typ},'trade_result':result},200 if result.get('success') else 400)
 except Exception as e:logging.exception('Webhook exception');return j({'success':False,'error':str(e)},500)
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
