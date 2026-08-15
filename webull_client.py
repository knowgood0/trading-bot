import os,json,sqlite3,urllib.request,uuid,time,threading
from datetime import datetime,timezone
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category

TRADE_DB='paper_trades.db'
GOOGLE_SHEETS_URL='https://script.google.com/macros/s/AKfycbzYocjcr-9_YTeaplxao7WLF6aNWi41fDb8z3evhcBot2cy3h9QrU9Q7iePIveY9_mC/exec'
WEBULL_ENDPOINT='api.sandbox.webull.com'
WEBULL_ACCOUNT_ID='DQIO6B3HUDJB14G6GF5K0J4J7B'
WEBULL_ACCOUNT_NUMBER='DEA73AV9'
WEBULL_ACCOUNT_NAME='Individual Margin'
_REQUEST_LOCK=threading.Lock(); _LAST_WEBULL_REQUEST=0.0; _MIN_WEBULL_REQUEST_INTERVAL=1.10
_SPY_CACHE={'price':None,'time':0.0}; _SPY_CACHE_SECONDS=2.5

def utc_now(): return datetime.now(timezone.utc).isoformat()
def make_client_order_id(prefix='TV'): return f'{prefix}{uuid.uuid4().hex.upper()}'[:32]
def _throttle_webull():
 global _LAST_WEBULL_REQUEST
 with _REQUEST_LOCK:
  wait=_MIN_WEBULL_REQUEST_INTERVAL-(time.monotonic()-_LAST_WEBULL_REQUEST)
  if wait>0: time.sleep(wait)
  _LAST_WEBULL_REQUEST=time.monotonic()
def _webull_call(fn,*args,**kwargs):
 last=None
 for attempt in range(3):
  try:
   _throttle_webull(); return fn(*args,**kwargs)
  except Exception as e:
   last=e; s=str(e)
   if '429' not in s and 'TOO_MANY_REQUESTS' not in s: raise
   time.sleep(2.0*(attempt+1))
 raise last

def _connect_db():
 c=sqlite3.connect(TRADE_DB); c.row_factory=sqlite3.Row; return c
def _ensure_database():
 c=_connect_db(); c.execute('''CREATE TABLE IF NOT EXISTS paper_trades (id INTEGER PRIMARY KEY AUTOINCREMENT,open INTEGER NOT NULL DEFAULT 0,contract TEXT,option_type TEXT,expiration TEXT,strike REAL,entry_price REAL,entry_premium REAL,entry_time TEXT,exit_price REAL,exit_premium REAL,profit_loss REAL,pricing_mode TEXT,result TEXT,error TEXT,created_at TEXT)'''); c.commit(); c.close()
def _row_to_dict(r):
 return None if r is None else {'id':r['id'],'open':bool(r['open']),'contract':r['contract'],'option_type':r['option_type'],'expiration':r['expiration'],'strike':r['strike'],'entry_price':r['entry_price'],'entry_premium':r['entry_premium'],'entry_time':r['entry_time'],'exit_price':r['exit_price'],'exit_premium':r['exit_premium'],'profit_loss':r['profit_loss'],'pricing_mode':r['pricing_mode'],'result':r['result'],'error':r['error']}
def load_open_trade():
 g=get_open_trade_from_google_sheets()
 if g:return g
 _ensure_database(); c=_connect_db(); r=c.execute('SELECT * FROM paper_trades WHERE open=1 ORDER BY id DESC LIMIT 1').fetchone(); c.close(); return _row_to_dict(r)
def load_latest_trade():
 _ensure_database(); c=_connect_db(); r=c.execute('SELECT * FROM paper_trades ORDER BY id DESC LIMIT 1').fetchone(); c.close(); return _row_to_dict(r)
def save_trade(t):
 _ensure_database(); c=_connect_db(); c.execute('INSERT INTO paper_trades (open,contract,option_type,expiration,strike,entry_price,entry_premium,entry_time,exit_price,exit_premium,profit_loss,pricing_mode,result,error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(1 if t.get('open') else 0,t.get('contract'),t.get('option_type'),t.get('expiration'),t.get('strike'),t.get('entry_price'),t.get('entry_premium'),t.get('entry_time'),t.get('exit_price'),t.get('exit_premium'),t.get('profit_loss'),t.get('pricing_mode'),t.get('result'),t.get('error'),utc_now())); c.commit(); t['id']=c.execute('SELECT last_insert_rowid()').fetchone()[0]; c.close()
def close_trade(i,ep,op,pl,pm):
 _ensure_database(); c=_connect_db(); c.execute("UPDATE paper_trades SET open=0,exit_price=?,exit_premium=?,profit_loss=?,pricing_mode=?,result='CLOSED' WHERE id=?",(ep,op,pl,pm,i)); c.commit(); c.close()
def get_trade_history(limit=50):
 _ensure_database(); c=_connect_db(); rows=c.execute('SELECT * FROM paper_trades ORDER BY id DESC LIMIT ?',(limit,)).fetchall(); c.close(); return [_row_to_dict(r) for r in rows]

def send_to_google_sheets(data):
 try:
  req=urllib.request.Request(GOOGLE_SHEETS_URL,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','User-Agent':'TradingBot/6.0'},method='POST')
  with urllib.request.urlopen(req,timeout=4) as r: body=r.read().decode()
  try:return json.loads(body)
  except:return {'success':True,'response':body}
 except Exception as e:return {'success':False,'error':str(e),'non_blocking':True}
def get_open_trade_from_google_sheets():
 try:
  req=urllib.request.Request(GOOGLE_SHEETS_URL+'?action=get_open_trade',headers={'User-Agent':'TradingBot/6.0'},method='GET')
  with urllib.request.urlopen(req,timeout=3) as r: x=json.loads(r.read().decode())
  return x.get('trade') if x.get('success') else None
 except:return None
def update_google_trade_closed(contract,exit_price,exit_premium,profit_loss,pricing_mode,result='CLOSED',error=''):
 return send_to_google_sheets({'action':'close_trade','contract':contract,'exit_price':exit_price,'exit_premium':exit_premium,'profit_loss':profit_loss,'pricing_mode':pricing_mode,'result':result,'error':error,'timestamp':utc_now()})
def journal_trade(event,action='',symbol='SPY',option_type='',contract='',expiration='',strike=None,spy_price=None,option_premium=None,entry_price=None,exit_price=None,profit_loss=None,pricing_mode='',result='',error=''):
 return send_to_google_sheets({'timestamp':utc_now(),'event':event,'action':action,'symbol':symbol,'option_type':option_type,'contract':contract,'expiration':expiration,'strike':strike,'spy_price':spy_price,'option_premium':option_premium,'entry_price':entry_price,'exit_price':exit_price,'profit_loss':profit_loss,'pricing_mode':pricing_mode,'result':result,'error':error})

def get_clients():
 key=os.environ.get('WEBULL_APP_KEY'); secret=os.environ.get('WEBULL_APP_SECRET')
 if not key: raise RuntimeError('WEBULL_APP_KEY environment variable is missing')
 if not secret: raise RuntimeError('WEBULL_APP_SECRET environment variable is missing')
 api=ApiClient(key,secret,'us'); api.add_endpoint('us',WEBULL_ENDPOINT)
 return TradeClient(api),DataClient(api)
def resolve_account():return {'account_id':WEBULL_ACCOUNT_ID,'account_number':WEBULL_ACCOUNT_NUMBER,'account_name':WEBULL_ACCOUNT_NAME,'environment':'SANDBOX'}
def test_webull_connection():
 try:
  tc,_=get_clients(); r=_webull_call(tc.account_v2.get_account_list); return {'success':True,'status_code':r.status_code,'account':r.json(),'configured_account':resolve_account(),'environment':'SANDBOX'}
 except Exception as e:return {'success':False,'error':str(e),'configured_account':resolve_account(),'environment':'SANDBOX'}
def _query_account(a,n):
 x={'account_name':n,'account_id':a,'balance':None,'positions':None,'balance_status':None,'positions_status':None,'errors':[]}
 try:
  tc,_=get_clients()
  try:r=_webull_call(tc.account_v2.get_account_balance,a);x['balance_status']=r.status_code;x['balance']=r.json()
  except Exception as e:x['errors'].append('BALANCE: '+str(e))
  try:r=_webull_call(tc.account_v2.get_account_position,a);x['positions_status']=r.status_code;x['positions']=r.json()
  except Exception as e:x['errors'].append('POSITIONS: '+str(e))
 except Exception as e:x['errors'].append('CLIENT: '+str(e))
 x['success']=x['balance_status']==200 and x['positions_status']==200; return x
def account_diagnostic():
 d={'success':False,'environment':'SANDBOX','endpoint':WEBULL_ENDPOINT,'configured_account':resolve_account(),'accounts':{},'account_list':None,'account_list_status':None,'error':None}
 try:
  tc,_=get_clients()
  try:r=_webull_call(tc.account_v2.get_account_list);d['account_list_status']=r.status_code;d['account_list']=r.json()
  except Exception as e:d['error']='ACCOUNT LIST: '+str(e)
  d['accounts']['configured']=_query_account(WEBULL_ACCOUNT_ID,WEBULL_ACCOUNT_NAME);d['success']=d['accounts']['configured'].get('success',False)
 except Exception as e:d['error']=str(e)
 return d

def account_order_capability_test():
 """
 READ-ONLY diagnostic. Does NOT submit any order.
 Reports configured account, environment, endpoint, and account diagnostic results.
 Explicitly states that no order was placed and does not claim order permissions.
 """
 diag = account_diagnostic()
 configured = resolve_account()
 account_list = diag.get('account_list')
 account_ids_from_list = []
 if isinstance(account_list, list):
  for a in account_list:
   if isinstance(a, dict) and a.get('account_id'):
    account_ids_from_list.append(a.get('account_id'))
 elif isinstance(account_list, dict):
  for key in ('account', 'accounts', 'data', 'items'):
   items = account_list.get(key)
   if isinstance(items, list):
    for a in items:
     if isinstance(a, dict) and a.get('account_id'):
      account_ids_from_list.append(a.get('account_id'))
    break

 configured_id = configured.get('account_id')
 id_present_in_list = configured_id in account_ids_from_list if account_ids_from_list else None

 notes = [
  'This endpoint is READ-ONLY. No order was submitted.',
  'Successful account lookup (HTTP 200) does NOT prove order permissions.',
  'Prior order attempts returned HTTP 403 ACCOUNT_ACCESS_DENIED — that is a separate issue to diagnose after this endpoint works.',
 ]
 if id_present_in_list is False:
  notes.append(
   'WARNING: configured account_id is NOT present in the account list returned by Webull. '
   'This mismatch is a likely contributor to ACCOUNT_ACCESS_DENIED on order placement.'
  )
 elif id_present_in_list is True:
  notes.append('Configured account_id appears in the account list returned by Webull.')
 else:
  notes.append('Could not determine whether configured account_id is present in the account list (list empty or unexpected shape).')

 return {
  'success': True,
  'endpoint': '/order-capability-test',
  'read_only': True,
  'order_submitted': False,
  'environment': 'SANDBOX',
  'webull_endpoint': WEBULL_ENDPOINT,
  'configured_account': configured,
  'account_diagnostic': diag,
  'account_ids_from_list': account_ids_from_list,
  'configured_id_present_in_list': id_present_in_list,
  'notes': notes,
  'message': 'Diagnostic only. No order was placed. Use this output to investigate 403 ACCOUNT_ACCESS_DENIED separately.',
 }

def inspect_order_api():
 """
 READ-ONLY inspection of order-related client attributes.
 Does NOT place any order. Useful for confirming SDK surface without side effects.
 """
 info = {
  'success': True,
  'read_only': True,
  'order_submitted': False,
  'environment': 'SANDBOX',
  'webull_endpoint': WEBULL_ENDPOINT,
  'configured_account': resolve_account(),
  'trade_client_attrs': [],
  'order_v3_attrs': [],
  'account_v2_attrs': [],
  'error': None,
  'notes': [
   'This endpoint is READ-ONLY. No order was submitted.',
   'Lists available attributes on TradeClient / order_v3 / account_v2 for diagnostics only.',
  ],
 }
 try:
  tc, _ = get_clients()
  info['trade_client_attrs'] = sorted([a for a in dir(tc) if not a.startswith('_')])
  if hasattr(tc, 'order_v3'):
   info['order_v3_attrs'] = sorted([a for a in dir(tc.order_v3) if not a.startswith('_')])
  if hasattr(tc, 'account_v2'):
   info['account_v2_attrs'] = sorted([a for a in dir(tc.account_v2) if not a.startswith('_')])
 except Exception as e:
  info['success'] = False
  info['error'] = str(e)
 return info

def get_webull_positions():
 try:tc,_=get_clients();r=_webull_call(tc.account_v2.get_account_position,WEBULL_ACCOUNT_ID);return {'success':True,'status_code':r.status_code,'account':resolve_account(),'positions':r.json()}
 except Exception as e:return {'success':False,'account':resolve_account(),'error':str(e)}
def get_webull_option_position(symbol):
 r=get_webull_positions()
 if not r.get('success'):return r
 p=r.get('positions')
 if isinstance(p,dict):
  for k in ('positions','data','items'):
   if isinstance(p.get(k),list):p=p[k];break
 if not isinstance(p,list):return {'success':True,'found':False,'symbol':symbol,'positions_response':r}
 m=[]
 for x in p:
  if not isinstance(x,dict):continue
  if str(x.get('symbol') or '')==symbol:m.append(x);continue
  for leg in x.get('legs') or []:
   if isinstance(leg,dict) and str(leg.get('symbol') or '')==symbol:m.append(x);break
 return {'success':True,'found':bool(m),'symbol':symbol,'positions':m}

def get_spy_price():
 if _SPY_CACHE['price'] is not None and time.monotonic()-_SPY_CACHE['time']<_SPY_CACHE_SECONDS:return {'success':True,'data':{'price':_SPY_CACHE['price'],'cached':True}}
 try:
  _,dc=get_clients();r=_webull_call(dc.market_data.get_snapshot,'SPY',Category.US_STOCK.name);d=r.json();p=d[0].get('price') if isinstance(d,list) and d else d.get('price') if isinstance(d,dict) else None
  if p is not None:_SPY_CACHE.update(price=float(p),time=time.monotonic())
  return {'success':True,'data':d}
 except Exception as e:return {'success':False,'error':str(e)}
def extract_spy_price():
 d=get_spy_price().get('data');
 try:return float(d[0]['price']) if isinstance(d,list) else float(d['price']) if isinstance(d,dict) else None
 except:return None

def get_option_contracts(option_type='CALL'):
 try:
  _,dc=get_clients();t=str(option_type).upper()
  if t not in ('CALL','PUT'):return {'error':'Invalid option type: '+t}
  today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
  r=_webull_call(dc.instrument.get_option_contracts,category=Category.US_OPTION.name,underlying_symbols='SPY',status='LISTING',start_date=today,end_date=today,option_type=t,style='AMERICAN',page_size=1000);d=r.json()
  if isinstance(d,dict) and isinstance(d.get('data'),list):return d['data']
  if isinstance(d,dict) and isinstance(d.get('items'),list):return d['items']
  return d
 except Exception as e:return {'error':str(e)}
def _select_contract_with_spy_price(t,spy):
 try:
  t=str(t).upper(); today=datetime.now(timezone.utc).strftime('%Y-%m-%d'); cs=get_option_contracts(t)
  if isinstance(cs,dict) and 'error' in cs:return {'success':False,'error':cs['error']}
  valid=[]
  for c in cs if isinstance(cs,list) else []:
   try:
    exp=str(c.get('expiration_date') or c.get('expiration') or '')[:10];strike=float(c['strike_price'])
    if str(c.get('def_type','')).upper()=='STANDARD' and str(c.get('style','')).upper()=='AMERICAN' and str(c.get('tradable_status','')).upper()=='OC' and str(c.get('option_type','')).upper()==t and exp==today:valid.append(c)
   except:pass
  if not valid:return {'success':False,'error':f'No valid 0DTE {t} contracts found for today'}
  valid.sort(key=lambda c:abs(float(c['strike_price'])-float(spy)));s=valid[0]
  return {'success':True,'spy_price':float(spy),'selected_contract':{'symbol':s.get('symbol'),'underlying_symbol':s.get('underlying_symbol','SPY'),'type':t,'strike':s.get('strike_price'),'expiration':s.get('expiration_date') or s.get('expiration'),'instrument_id':s.get('instrument_id'),'underlying_instrument_id':s.get('underlying_instrument_id'),'raw':s}}
 except Exception as e:return {'success':False,'error':str(e)}
def select_0dte_atm_contract(t='CALL'):
 p=extract_spy_price();return {'success':False,'error':'Unable to get current SPY price'} if p is None else _select_contract_with_spy_price(t,p)
def select_contract(option_type='CALL'):return select_0dte_atm_contract(option_type)
def get_option_price(symbol):
 try:
  _,dc=get_clients();r=_webull_call(dc.option_market_data.get_option_snapshot,symbol,Category.US_OPTION.name);d=r.json();item=d[0] if isinstance(d,list) and d else d if isinstance(d,dict) else {};premium=None
  for f in ('price','latest_price','last_price','last','close','mark_price'):
   if item.get(f) is not None:premium=float(item[f]);break
  return {'success':True,'premium':premium,'data':d}
 except Exception as e:return {'success':False,'premium':None,'error':str(e)}

# CRITICAL OPTION ORDER FIX: the leg symbol is the UNDERLYING (SPY), not
# SPY260814C00777000. Webull's official v3 option schema requires the same
# underlying symbol at top level and in the option leg, with strike/date/type
# identifying the option. position_intent is also sent as documented.
def _webull_place_option_order(option_symbol,option_type,side,quantity,limit_price,position_intent,strike_price,expiration,underlying_symbol='SPY'):
 try:
  tc,_=get_clients();t=str(option_type).upper();s=str(side).upper();intent=str(position_intent).upper();under=str(underlying_symbol or 'SPY').upper()
  if t not in ('CALL','PUT') or s not in ('BUY','SELL'):return {'success':False,'error':'Invalid option type or side'}
  if intent not in ('BUY_TO_OPEN','BUY_TO_CLOSE','SELL_TO_OPEN','SELL_TO_CLOSE'):return {'success':False,'error':'Invalid position intent'}
  if limit_price is None or strike_price is None or expiration is None:return {'success':False,'error':'Missing option order field'}
  cid=make_client_order_id('TV')
  order={'client_order_id':cid,'combo_type':'NORMAL','option_strategy':'SINGLE','instrument_type':'OPTION','entrust_type':'QTY','symbol':under,'market':'US','side':s,'order_type':'LIMIT','limit_price':f'{float(limit_price):.2f}','quantity':str(int(quantity)),'time_in_force':'DAY','position_intent':intent,'legs':[{'side':s,'quantity':str(int(quantity)),'symbol':under,'strike_price':f'{float(strike_price):.2f}','option_expire_date':str(expiration)[:10],'instrument_type':'OPTION','option_type':t,'market':'US'}]}
  r=_webull_call(tc.order_v3.place_order,WEBULL_ACCOUNT_ID,[order])
  try:d=r.json()
  except:d={'raw':str(r)}
  ok=200<=r.status_code<300
  return {'success':ok,'accepted':ok,'status_code':r.status_code,'client_order_id':cid,'account':resolve_account(),'response':d,'prepared_order':order,'option_contract_symbol':option_symbol,'order_status_note':'Accepted/submitted; this does not mean filled.' if ok else 'Webull did not accept the order request.'}
 except Exception as e:return {'success':False,'accepted':False,'account':resolve_account(),'error':str(e)}
def test_order_detail(client_order_id):
 try:tc,_=get_clients();r=_webull_call(tc.order_v3.get_order_detail,WEBULL_ACCOUNT_ID,client_order_id);return {'success':200<=r.status_code<300,'status_code':r.status_code,'account':resolve_account(),'client_order_id':client_order_id,'order':r.json()}
 except Exception as e:return {'success':False,'account':resolve_account(),'error':str(e)}

def paper_buy_spy(option_type='CALL'):
 t=str(option_type).upper()
 if t not in ('CALL','PUT'):return {'success':False,'error':'Option type must be CALL or PUT'}
 existing=load_open_trade()
 if existing:return {'success':False,'error':'A logged paper trade is already open.','trade':existing}
 spy=extract_spy_price()
 if spy is None:return {'success':False,'error':'Unable to get current SPY price'}
 cr=_select_contract_with_spy_price(t,spy)
 if not cr.get('success'):return cr
 sel=cr['selected_contract'];symbol=sel.get('symbol');exp=sel.get('expiration');strike=sel.get('strike');under=sel.get('underlying_symbol','SPY')
 if not symbol or strike is None or exp is None:return {'success':False,'error':'Selected option is missing symbol, strike, or expiration'}
 pr=get_option_price(symbol);premium=pr.get('premium')
 if premium is None:return {'success':False,'error':'Unable to obtain option premium. No Webull order submitted.','contract':symbol,'premium':pr}
 order=_webull_place_option_order(symbol,t,'BUY',1,premium,'BUY_TO_OPEN',strike,exp,under)
 if not order.get('success'):
  journal_trade('WEBULL_BUY_FAILED','BUY','SPY',t,symbol,exp,strike,spy,premium,result='FAILED',error=str(order.get('response') or order.get('error')))
  return {'success':False,'message':'Webull Sandbox LIMIT BUY was NOT accepted','contract':symbol,'premium':premium,'order':order}
 trade={'open':True,'contract':symbol,'option_type':t,'expiration':exp,'strike':strike,'entry_price':spy,'entry_premium':premium,'entry_time':utc_now(),'exit_price':None,'exit_premium':None,'profit_loss':None,'pricing_mode':'OPTION_PREMIUM','result':'OPEN','error':None,'order_status':'SUBMITTED','client_order_id':order.get('client_order_id')}
 save_trade(trade);g=journal_trade('WEBULL_BUY','BUY','SPY',t,symbol,exp,strike,spy,premium,entry_price=spy,pricing_mode='OPTION_PREMIUM',result='OPEN')
 return {'success':True,'message':'Webull Sandbox LIMIT BUY accepted/submitted; fill status must be checked separately','account':resolve_account(),'trade':trade,'order':order,'google_sheets':g}
def paper_sell_spy():
 trade=load_open_trade()
 if not trade:return {'success':False,'error':'No logged open trade'}
 spy=extract_spy_price();symbol=trade.get('contract')
 if spy is None or not symbol:return {'success':False,'error':'Unable to get SPY price or missing contract'}
 pr=get_option_price(symbol);premium=pr.get('premium');entry=trade.get('entry_premium')
 if premium is None or entry in (None,0):return {'success':False,'error':'Unable to obtain current option premium or missing entry premium'}
 pl=round(((premium-entry)/entry)*100,2);t=str(trade.get('option_type','CALL')).upper();order=_webull_place_option_order(symbol,t,'SELL',1,premium,'SELL_TO_CLOSE',trade.get('strike'),trade.get('expiration'),'SPY')
 if not order.get('success'):return {'success':False,'message':'Webull Sandbox LIMIT SELL was NOT accepted','contract':symbol,'order':order}
 g=update_google_trade_closed(symbol,spy,premium,pl,'OPTION_PREMIUM','CLOSED','');
 if trade.get('id') is not None:
  try:close_trade(trade['id'],spy,premium,pl,'OPTION_PREMIUM')
  except:pass
 return {'success':True,'message':'Webull Sandbox LIMIT SELL accepted/submitted; fill status must be checked separately','account':resolve_account(),'trade':{'contract':symbol,'option_type':t,'entry_price':trade.get('entry_price'),'entry_premium':entry,'exit_price':spy,'exit_premium':premium,'profit_loss':pl,'pricing_mode':'OPTION_PREMIUM','result':'CLOSED'},'order':order,'google_sheets':g}

def get_persistent_open_trade():return get_open_trade_from_google_sheets()
def test_google_sheets_connection():return {'success':True,'open_trade':get_open_trade_from_google_sheets()}
def paper_trade_status():return {'success':True,'open_trade':load_open_trade(),'account':resolve_account()}
def debug_option_chain():
 c=get_option_contracts('CALL');return {'success':not(isinstance(c,dict) and 'error' in c),'contracts':c}
def debug_market_data():return get_spy_price()
def test_options():
 spy=extract_spy_price()
 if spy is None:return {'success':False,'error':'Unable to get SPY price for option test'}
 call=_select_contract_with_spy_price('CALL',spy);time.sleep(1.5);put=_select_contract_with_spy_price('PUT',spy)
 return {'success':call.get('success',False) and put.get('success',False),'spy_price':spy,'call':call,'put':put}
