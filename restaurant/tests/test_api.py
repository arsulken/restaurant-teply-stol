import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import create_app

class RestaurantTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.app=create_app(Path(self.temp.name)/'test.db'); self.client=self.app.test_client()
  self.token=self.login('client'); self.admin=self.login('admin')
 def tearDown(self): self.temp.cleanup()
 def login(self,role):
  r=self.client.post('/api/auth/login',json={'email':role+'@restaurant.test','password':role.title()+'123!'})
  self.assertEqual(r.status_code,200); return r.json['token']
 def req(self,path,method='GET',body=None,token=None):
  return self.client.open('/api'+path,method=method,json=body,headers={'Authorization':'Bearer '+(token or self.token)})
 def order(self,q=2):
  self.assertEqual(self.req('/cart/1','PUT',{'quantity':q}).status_code,200)
  r=self.req('/orders','POST',{}); self.assertEqual(r.status_code,201);return r.json
 def stock(self):return self.client.get('/api/dishes').json[0]['stock']
 def test_01_guest_menu(self):self.assertEqual(len(self.client.get('/api/dishes').json),8)
 def test_02_guest_cart_denied(self):self.assertEqual(self.client.get('/api/cart').status_code,401)
 def test_03_registration_cannot_grant_admin(self):
  r=self.client.post('/api/auth/register',json={'name':'Студент','email':'new@test.test','password':'Password1','role':'admin'})
  self.assertEqual(r.status_code,201);self.assertEqual(r.json['user']['role'],'client')
 def test_04_duplicate_email(self):
  r=self.client.post('/api/auth/register',json={'name':'Студент','email':'client@restaurant.test','password':'Password1'})
  self.assertEqual(r.status_code,409)
 def test_05_bad_password(self):
  self.assertEqual(self.client.post('/api/auth/login',json={'email':'client@restaurant.test','password':'wrongpass'}).status_code,401)
  self.client.post('/api/auth/register',json={'name':'Пробел','email':'space@test.test','password':' password1 '})
  self.assertEqual(self.client.post('/api/auth/login',json={'email':'space@test.test','password':' password1 '}).status_code,200)
 def test_06_client_admin_denied(self):self.assertEqual(self.req('/admin/orders').status_code,403)
 def test_07_cart_total(self):
  r=self.req('/cart/1','PUT',{'quantity':2});self.assertEqual(r.json['total'],58000)
 def test_08_invalid_quantities(self):
  for q in [0,-1,100,1.2,True,'2',None]:self.assertEqual(self.req('/cart/1','PUT',{'quantity':q}).status_code,400)
 def test_09_stock_limit(self):self.assertEqual(self.req('/cart/1','PUT',{'quantity':21}).status_code,409)
 def test_10_empty_cart(self):self.assertEqual(self.req('/orders','POST',{}).status_code,400)
 def test_11_checkout_atomic(self):
  o=self.order();self.assertEqual(o['total'],58000);self.assertEqual(self.stock(),18);self.assertEqual(self.req('/cart').json['items'],[])
 def test_12_cancel_restores_once(self):
  o=self.order();p=f'/orders/{o["id"]}/cancel';self.assertEqual(self.req(p,'POST',{}).status_code,200);self.assertEqual(self.stock(),20);self.assertEqual(self.req(p,'POST',{}).status_code,409);self.assertEqual(self.stock(),20)
 def test_13_other_user_cannot_cancel(self):
  o=self.order();self.assertEqual(self.req(f'/orders/{o["id"]}/cancel','POST',{},self.admin).status_code,404)
 def test_14_status_workflow(self):
  o=self.order();p=f'/admin/orders/{o["id"]}/status';self.assertEqual(self.req(p,'PATCH',{'status':'completed'},self.admin).status_code,409)
  for s in ['cooking','ready','completed']:self.assertEqual(self.req(p,'PATCH',{'status':s},self.admin).status_code,200)
  self.assertEqual(self.req(f'/orders/{o["id"]}/cancel','POST',{}).status_code,409)
 def test_15_admin_can_purchase(self):
  self.assertEqual(self.req('/cart/2','PUT',{'quantity':1},self.admin).status_code,200)
  self.assertEqual(self.req('/orders','POST',{},self.admin).status_code,201)
 def test_16_edit_order(self):
  o=self.order();r=self.req(f'/admin/orders/{o["id"]}/items','PUT',{'items':[{'dish_id':2,'quantity':1}]},self.admin)
  self.assertEqual(r.status_code,200);self.assertEqual(self.stock(),20);self.assertEqual(self.req('/orders').json[0]['total'],39000)
 def test_17_failed_edit_rolls_back(self):
  o=self.order();r=self.req(f'/admin/orders/{o["id"]}/items','PUT',{'items':[{'dish_id':2,'quantity':99}]},self.admin)
  self.assertEqual(r.status_code,409);self.assertEqual(self.stock(),18);self.assertEqual(self.req('/orders').json[0]['total'],58000)
 def test_18_changed_stock_checkout_rolls_back(self):
  self.req('/cart/1','PUT',{'quantity':2});d=self.client.get('/api/dishes').json[0];d['stock']=1
  self.req('/admin/dishes/1','PUT',d,self.admin);self.assertEqual(self.req('/orders','POST',{}).status_code,409);self.assertEqual(self.stock(),1);self.assertEqual(self.req('/orders').json,[]);self.assertEqual(len(self.req('/cart').json['items']),1)
 def test_19_price_snapshot(self):
  o=self.order();d=self.client.get('/api/dishes').json[0];d['price']=99000;self.req('/admin/dishes/1','PUT',d,self.admin);self.assertEqual(self.req('/orders').json[0]['total'],58000)
 def test_20_logout_invalidates_token(self):
  self.assertEqual(self.req('/auth/logout','POST',{}).status_code,204);self.assertEqual(self.req('/cart').status_code,401)
 def test_21_admin_add_dish(self):
  d={'name':'Чай','category':'Напитки','description':'Чёрный чай','price':15000,'stock':8};self.assertEqual(self.req('/admin/dishes','POST',d,self.admin).status_code,201)
 def test_22_invalid_price(self):
  d=self.client.get('/api/dishes').json[0];d['price']=-1;self.assertEqual(self.req('/admin/dishes/1','PUT',d,self.admin).status_code,400)
 def test_23_cors(self):
  r=self.client.options('/api/cart',headers={'Origin':'http://127.0.0.1:8080'});self.assertEqual(r.status_code,204);self.assertEqual(r.headers['Access-Control-Allow-Origin'],'http://127.0.0.1:8080')
 def test_24_isolation_and_malformed_json(self):
  self.order();self.assertEqual(self.req('/orders',token=self.admin).json,[])
  self.assertEqual(self.req('/cart/1','PUT',[]).status_code,400)

if __name__=='__main__':unittest.main(verbosity=2)
