"""Учебный REST API ресторана. Запуск: python app.py"""
import os, re, sqlite3, secrets, time
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parent
MENU = [
 ('Брускетта с томатами','Закуски','Чиабатта, томаты, базилик, оливковое масло. Содержит глютен.',29000,20),
 ('Салат с печёной свёклой','Закуски','Свёкла, руккола, мягкий сыр, грецкий орех. Молоко, орехи.',39000,15),
 ('Тыквенный крем-суп','Супы','Тыква, сливки, семечки и хрустящий хлеб. Молоко, глютен.',35000,18),
 ('Куриный суп с лапшой','Супы','Куриный бульон, домашняя лапша, зелень. Глютен, яйцо.',32000,20),
 ('Паста с грибами','Горячее','Паста, шампиньоны, сливочный соус, пармезан. Глютен, молоко.',59000,15),
 ('Курица с картофелем','Горячее','Запечённое филе, картофель, травы, сливочный соус. Молоко.',62000,12),
 ('Чизкейк','Десерты','Сливочный сыр, песочная основа, ягодный соус. Молоко, яйцо, глютен.',36000,10),
 ('Ягодный морс','Напитки','Клюква, смородина, вода, сахар. Порция 300 мл.',18000,30)]

class ApiError(Exception):
 def __init__(self, message, status=400): self.message, self.status = message, status

def create_app(database=None):
 app = Flask(__name__)
 app.config.update(DATABASE=str(database or os.environ.get('RESTAURANT_DB',ROOT/'restaurant.db')), MAX_CONTENT_LENGTH=32768)
 with sqlite3.connect(app.config['DATABASE']) as db:
  db.executescript((ROOT/'schema.sql').read_text())
  if not db.execute('SELECT 1 FROM dishes').fetchone(): db.executemany('INSERT INTO dishes(name,category,description,price,stock) VALUES(?,?,?,?,?)', MENU)
  if not db.execute('SELECT 1 FROM users').fetchone():
   for name,email,password,role in [('Администратор','admin@restaurant.test','Admin123!','admin'),('Клиент','client@restaurant.test','Client123!','client')]:
    db.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),role))
 def db():
  if 'db' not in g:
   g.db=sqlite3.connect(app.config['DATABASE'],timeout=10); g.db.row_factory=sqlite3.Row
   g.db.execute('PRAGMA foreign_keys=ON')
  return g.db
 @app.teardown_appcontext
 def close(_):
  if 'db' in g: g.db.close()
 @app.before_request
 def cors_preflight():
  if request.method=='OPTIONS': return '',204
 @app.after_request
 def cors(response):
  if request.headers.get('Origin') in ('http://127.0.0.1:8080','http://localhost:8080'):
   response.headers['Access-Control-Allow-Origin']=request.headers['Origin']
   response.headers['Vary']='Origin'
   response.headers['Access-Control-Allow-Headers']='Authorization, Content-Type'
   response.headers['Access-Control-Allow-Methods']='GET, POST, PUT, PATCH, DELETE, OPTIONS'
  response.headers['Cache-Control']='no-store'
  response.headers['X-Content-Type-Options']='nosniff'
  return response
 @app.errorhandler(ApiError)
 def api_error(e): return jsonify(error=e.message),e.status
 @app.errorhandler(HTTPException)
 def http_error(e): return jsonify(error='Некорректный запрос' if e.code==400 else e.description),e.code
 def data():
  x=request.get_json(silent=True)
  if not isinstance(x,dict): raise ApiError('Ожидается JSON-объект')
  return x
 def integer(x, lo, hi, label):
  if type(x) is not int or not lo<=x<=hi: raise ApiError(f'{label}: целое число от {lo} до {hi}')
  return x
 def string(x,lo,hi,label):
  if not isinstance(x,str) or not lo<=len(x.strip())<=hi: raise ApiError(f'{label}: от {lo} до {hi} символов')
  return x.strip()
 def auth(admin=False):
  def decorate(fn):
   @wraps(fn)
   def wrapped(*args,**kwargs):
    token=request.headers.get('Authorization','').removeprefix('Bearer ')
    g.user=db().execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?',(token,int(time.time()))).fetchone()
    if not g.user: raise ApiError('Войдите в аккаунт',401)
    if admin and g.user['role']!='admin': raise ApiError('Недостаточно прав',403)
    return fn(*args,**kwargs)
   return wrapped
  return decorate
 def public_user(u): return {k:u[k] for k in ['id','name','email','role']}
 def session(u):
  token=secrets.token_urlsafe(32)
  db().execute('INSERT INTO sessions VALUES(?,?,?)',(token,u['id'],int(time.time())+28800)); db().commit()
  return jsonify(token=token,user=public_user(u))
 @app.get('/api/health')
 def health(): return jsonify(status='ok')
 @app.post('/api/auth/register')
 def register():
  x=data(); name=string(x.get('name'),2,60,'Имя'); email=string(x.get('email'),5,120,'Email').lower(); password=x.get('password')
  if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ApiError('Некорректный email')
  if not isinstance(password,str) or not 8<=len(password)<=128: raise ApiError('Пароль должен содержать от 8 до 128 символов')
  try:
   cur=db().execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash(password),'client')); db().commit()
  except sqlite3.IntegrityError: raise ApiError('Этот email уже зарегистрирован',409)
  return session(db().execute('SELECT * FROM users WHERE id=?',(cur.lastrowid,)).fetchone()),201
 @app.post('/api/auth/login')
 def login():
  x=data(); email=string(x.get('email'),1,120,'Email').lower(); password=x.get('password')
  if not isinstance(password,str) or not 1<=len(password)<=128: raise ApiError('Некорректный пароль')
  u=db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
  if not u or not check_password_hash(u['password_hash'],password): raise ApiError('Неверный email или пароль',401)
  return session(u)
 @app.get('/api/auth/me')
 @auth()
 def me(): return jsonify(public_user(g.user))
 @app.post('/api/auth/logout')
 @auth()
 def logout():
  db().execute('DELETE FROM sessions WHERE token=?',(request.headers['Authorization'].removeprefix('Bearer '),)); db().commit(); return '',204
 @app.get('/api/dishes')
 def dishes(): return jsonify([dict(r) for r in db().execute('SELECT * FROM dishes ORDER BY id')])
 def dish_fields(x):
  return (string(x.get('name'),2,80,'Название'),string(x.get('category'),2,40,'Категория'),string(x.get('description'),2,500,'Состав'),integer(x.get('price'),1,10000000,'Цена в копейках'),integer(x.get('stock'),0,10000,'Остаток'))
 @app.post('/api/admin/dishes')
 @auth(True)
 def add_dish():
  cur=db().execute('INSERT INTO dishes(name,category,description,price,stock) VALUES(?,?,?,?,?)',dish_fields(data())); db().commit(); return jsonify(id=cur.lastrowid),201
 @app.put('/api/admin/dishes/<int:did>')
 @auth(True)
 def edit_dish(did):
  cur=db().execute('UPDATE dishes SET name=?,category=?,description=?,price=?,stock=? WHERE id=?',(*dish_fields(data()),did))
  if not cur.rowcount: raise ApiError('Блюдо не найдено',404)
  db().commit(); return jsonify(ok=True)
 def cart_rows():
  return [dict(r) for r in db().execute('SELECT d.*,c.quantity FROM cart_items c JOIN dishes d ON c.dish_id=d.id WHERE c.user_id=? ORDER BY d.id',(g.user['id'],))]
 @app.get('/api/cart')
 @auth()
 def cart():
  items=cart_rows(); return jsonify(items=items,total=sum(i['quantity']*i['price'] for i in items))
 @app.put('/api/cart/<int:did>')
 @auth()
 def update_cart(did):
  q=integer(data().get('quantity'),1,99,'Количество'); row=db().execute('SELECT stock FROM dishes WHERE id=?',(did,)).fetchone()
  if not row: raise ApiError('Блюдо не найдено',404)
  if q>row['stock']: raise ApiError('Недостаточно порций',409)
  db().execute('INSERT INTO cart_items VALUES(?,?,?) ON CONFLICT(user_id,dish_id) DO UPDATE SET quantity=excluded.quantity',(g.user['id'],did,q)); db().commit(); return cart()
 @app.delete('/api/cart/<int:did>')
 @auth()
 def delete_cart(did):
  db().execute('DELETE FROM cart_items WHERE user_id=? AND dish_id=?',(g.user['id'],did)); db().commit(); return '',204
 def order_dict(r):
  x=dict(r); x['items']=[dict(i) for i in db().execute('SELECT * FROM order_items WHERE order_id=?',(r['id'],))]; return x
 @app.get('/api/orders')
 @auth()
 def orders(): return jsonify([order_dict(r) for r in db().execute('SELECT * FROM orders WHERE user_id=? ORDER BY id DESC',(g.user['id'],))])
 def reserve(items,oid):
  total=0
  for i in items:
   d=db().execute('SELECT * FROM dishes WHERE id=?',(i['dish_id'],)).fetchone()
   if not d: raise ApiError('Блюдо не найдено',404)
   if d['stock']<i['quantity']: raise ApiError(f'Недостаточно порций: {d["name"]}',409)
   db().execute('UPDATE dishes SET stock=stock-? WHERE id=?',(i['quantity'],d['id']))
   db().execute('INSERT INTO order_items(order_id,dish_id,name,price,quantity) VALUES(?,?,?,?,?)',(oid,d['id'],d['name'],d['price'],i['quantity']))
   total+=d['price']*i['quantity']
  return total
 @app.post('/api/orders')
 @auth()
 def checkout():
  comment=string(data().get('comment',''),0,300,'Комментарий'); db().execute('BEGIN IMMEDIATE')
  items=cart_rows()
  if not items: raise ApiError('Корзина пуста')
  cur=db().execute('INSERT INTO orders(user_id,status,total,created_at,comment) VALUES(?,?,?,?,?)',(g.user['id'],'new',1,datetime.now(timezone.utc).isoformat(),comment)); oid=cur.lastrowid
  total=reserve([{'dish_id':i['id'],'quantity':i['quantity']} for i in items],oid)
  db().execute('UPDATE orders SET total=? WHERE id=?',(total,oid)); db().execute('DELETE FROM cart_items WHERE user_id=?',(g.user['id'],)); db().commit()
  return jsonify(order_dict(db().execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())),201
 def load_order(oid,own=False):
  r=db().execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
  if not r or (own and r['user_id']!=g.user['id']): raise ApiError('Заказ не найден',404)
  return r
 def restore(oid):
  for i in db().execute('SELECT dish_id,quantity FROM order_items WHERE order_id=?',(oid,)).fetchall(): db().execute('UPDATE dishes SET stock=stock+? WHERE id=?',(i['quantity'],i['dish_id']))
 @app.post('/api/orders/<int:oid>/cancel')
 @auth()
 def cancel(oid):
  db().execute('BEGIN IMMEDIATE'); r=load_order(oid,True)
  if r['status']!='new': raise ApiError('Можно отменить только новый заказ',409)
  restore(oid); db().execute("UPDATE orders SET status='cancelled' WHERE id=?",(oid,)); db().commit(); return jsonify(ok=True)
 @app.get('/api/admin/orders')
 @auth(True)
 def all_orders(): return jsonify([order_dict(r) for r in db().execute('SELECT o.*,u.name AS customer FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.id DESC')])
 @app.patch('/api/admin/orders/<int:oid>/status')
 @auth(True)
 def status(oid):
  x=data(); target=x.get('status'); db().execute('BEGIN IMMEDIATE'); r=load_order(oid)
  transitions={'new':['cooking','cancelled'],'cooking':['ready'],'ready':['completed'],'completed':[],'cancelled':[]}
  if target not in transitions[r['status']]: raise ApiError('Недопустимый переход статуса',409)
  if target=='cancelled': restore(oid)
  db().execute('UPDATE orders SET status=? WHERE id=?',(target,oid)); db().commit(); return jsonify(ok=True)
 @app.put('/api/admin/orders/<int:oid>/items')
 @auth(True)
 def edit_items(oid):
  items=data().get('items')
  if not isinstance(items,list) or not 1<=len(items)<=50: raise ApiError('Нужно от 1 до 50 позиций')
  normalized=[]; seen=set()
  for i in items:
   if not isinstance(i,dict): raise ApiError('Некорректная позиция')
   did=integer(i.get('dish_id'),1,1000000,'ID блюда'); q=integer(i.get('quantity'),1,99,'Количество')
   if did in seen: raise ApiError('Блюда не должны повторяться')
   seen.add(did); normalized.append({'dish_id':did,'quantity':q})
  db().execute('BEGIN IMMEDIATE'); r=load_order(oid)
  if r['status']!='new': raise ApiError('Состав можно менять только до приготовления',409)
  restore(oid); db().execute('DELETE FROM order_items WHERE order_id=?',(oid,)); total=reserve(normalized,oid)
  db().execute('UPDATE orders SET total=? WHERE id=?',(total,oid)); db().commit(); return jsonify(ok=True)
 return app

if __name__=='__main__': create_app().run(host='127.0.0.1',port=int(os.environ.get('PORT','8000')),debug=False)
