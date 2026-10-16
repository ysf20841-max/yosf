import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'smm_panel_super_secret_key_2026'
DB_NAME = 'smm_store.db'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

USD_TO_SYP = 150.0

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            gender TEXT DEFAULT 'male',
            balance REAL DEFAULT 0.0,
            spent_amount REAL DEFAULT 0.0,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            image_url TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_usd REAL NOT NULL,
            price_syp REAL DEFAULT 0.0,
            input_type TEXT NOT NULL,
            category_image_url TEXT,
            service_image_url TEXT,
            is_available INTEGER DEFAULT 1,
            provider_api_url TEXT NOT NULL,
            provider_api_key TEXT NOT NULL,
            provider_service_id TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_id TEXT NOT NULL,
            requested_amount REAL NOT NULL,
            approved_amount REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            target_input TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            status TEXT DEFAULT 'قيد الانتظار',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, email, password, gender, balance, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
                       ('admin', 'admin@store.com', 'admin123', 'male', 1000.0, 1))
        
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات تلقائياً عند تشغيل السيرفر على السحابة
with app.app_context():
    init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT category, category_image_url FROM services")
    services_cats = cursor.fetchall()
    
    cats_dict = {}
    for row in services_cats:
        cats_dict[row['category']] = row['category_image_url']
        
    cursor.execute("SELECT * FROM categories")
    for row in cursor.fetchall():
        if row['name'] not in cats_dict or not cats_dict[row['name']]:
            cats_dict[row['name']] = row['image_url']
            
    final_categories = [{'name': k, 'image_url': v} for k, v in cats_dict.items()]
    
    user = None
    if 'user_id' in session:
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        
    conn.close()
    return render_template('index.html', categories=final_categories, current_user=user, usd_to_syp=USD_TO_SYP)

@app.route('/category/<path:cat_name>')
def category_services(cat_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services WHERE category = ?", (cat_name,))
    services = [dict(row) for row in cursor.fetchall()]
    
    user = None
    if 'user_id' in session:
        cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
    conn.close()
    return render_template('category_services.html', category_name=cat_name, services=services, current_user=user, usd_to_syp=USD_TO_SYP)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        gender = request.form.get('gender', 'male')
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password, gender) VALUES (?, ?, ?, ?)",
                           (username, email, password, gender))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            new_user = cursor.fetchone()
            session['user_id'] = new_user['id']
            session['username'] = new_user['username']
            flash('تم إنشاء الحساب بنجاح!', 'success')
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('اسم المستخدم أو البريد مستخدم مسبقاً', 'danger')
        finally:
            conn.close()
    return render_template('register.html', usd_to_syp=USD_TO_SYP)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('بيانات الدخول غير صحيحة', 'danger')
    return render_template('login.html', usd_to_syp=USD_TO_SYP)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج', 'info')
    return redirect(url_for('index'))

@app.route('/my-orders')
@login_required
def my_orders():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (session['user_id'],))
    orders = cursor.fetchall()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return render_template('my_orders.html', orders=orders, current_user=user, usd_to_syp=USD_TO_SYP)

@app.route('/order', methods=['POST'])
@login_required
def place_order():
    service_id = request.form.get('service_id')
    target_input = request.form.get('target_input')
    quantity = int(request.form.get('quantity', 0))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
    service = cursor.fetchone()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    
    if not service or not service['is_available']:
        flash('الخدمة غير متوفرة', 'danger')
        conn.close()
        return redirect(url_for('index'))
        
    total_price = (service['price_usd'] / 1000.0) * quantity
    
    if user['balance'] < total_price:
        flash(f'رصيد المحفظة غير كافٍ. المطلوب: ${total_price:.2f}', 'danger')
        conn.close()
        return redirect(url_for('deposit'))
        
    new_balance = user['balance'] - total_price
    new_spent = user['spent_amount'] + total_price
    cursor.execute("UPDATE users SET balance = ?, spent_amount = ? WHERE id = ?", (new_balance, new_spent, user['id']))
    cursor.execute("INSERT INTO orders (user_id, service_name, target_input, quantity, total_price, status) VALUES (?, ?, ?, ?, ?, ?)",
                   (user['id'], service['name'], target_input, quantity, total_price, 'قيد التنفيذ'))
    
    try:
        requests.post(service['provider_api_url'], data={
            'key': service['provider_api_key'],
            'action': 'add',
            'service': service['provider_service_id'],
            'link': target_input,
            'quantity': quantity
        }, timeout=10)
    except Exception:
        pass

    conn.commit()
    conn.close()
    flash('تم إرسال الطلب بنجاح!', 'success')
    return redirect(url_for('my_orders'))

@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'POST':
        tx_id = request.form.get('tx_id')
        amount = float(request.form.get('amount') or 0.0)
        cursor.execute("INSERT INTO deposits (user_id, tx_id, requested_amount) VALUES (?, ?, ?)",
                       (session['user_id'], tx_id, amount))
        conn.commit()
        flash('تم إرسال طلب الشحن بنجاح بانتظار التأكيد', 'success')
        conn.close()
        return redirect(url_for('deposit'))
        
    cursor.execute("SELECT * FROM deposits WHERE user_id = ? ORDER BY id DESC", (session['user_id'],))
    user_deposits = cursor.fetchall()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return render_template('deposit.html', deposits=user_deposits, current_user=user, usd_to_syp=USD_TO_SYP)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    current_user = cursor.fetchone()
    if not current_user or not current_user['is_admin']:
        flash('غير مصرح لك', 'danger')
        conn.close()
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_service':
            name = request.form.get('name')
            category = request.form.get('category')
            price_usd = float(request.form.get('price_usd') or 0.0)
            price_syp = price_usd * USD_TO_SYP
            input_type = request.form.get('input_type')
            
            cat_image_url = ""
            file_cat = request.files.get('category_image_file')
            if file_cat and file_cat.filename != '':
                fname_cat = secure_filename(file_cat.filename)
                file_cat.save(os.path.join(app.config['UPLOAD_FOLDER'], fname_cat))
                cat_image_url = url_for('static', filename='uploads/' + fname_cat)

            serv_image_url = ""
            file_serv = request.files.get('service_image_file')
            if file_serv and file_serv.filename != '':
                fname_serv = secure_filename(file_serv.filename)
                file_serv.save(os.path.join(app.config['UPLOAD_FOLDER'], fname_serv))
                serv_image_url = url_for('static', filename='uploads/' + fname_serv)

            cursor.execute('''
                INSERT INTO services (name, category, price_usd, price_syp, input_type, category_image_url, service_image_url, provider_api_url, provider_api_key, provider_service_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, category, price_usd, price_syp, input_type, cat_image_url, serv_image_url, request.form.get('provider_api_url'), request.form.get('provider_api_key'), request.form.get('provider_service_id')))
            conn.commit()
            flash('تمت إضافة الخدمة وصورها بنجاح', 'success')
            
        elif action == 'toggle_status':
            sid = request.form.get('service_id')
            status = int(request.form.get('current_status'))
            cursor.execute("UPDATE services SET is_available = ? WHERE id = ?", (0 if status == 1 else 1, sid))
            conn.commit()
            
        elif action == 'approve_deposit':
            dep_id = request.form.get('deposit_id')
            app_amt = float(request.form.get('approved_amount') or 0.0)
            cursor.execute("SELECT * FROM deposits WHERE id = ?", (dep_id,))
            dep = cursor.fetchone()
            if dep and dep['status'] == 'pending':
                cursor.execute("UPDATE deposits SET status = 'approved', approved_amount = ? WHERE id = ?", (app_amt, dep_id))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (app_amt, dep['user_id']))
                conn.commit()
                flash('تم اعتماد الشحن وإضافته للمحفظة', 'success')

    cursor.execute("SELECT * FROM services")
    services = cursor.fetchall()
    cursor.execute("SELECT deposits.*, users.username FROM deposits JOIN users ON deposits.user_id = users.id ORDER BY deposits.id DESC")
    deposits = cursor.fetchall()
    conn.close()
    return render_template('admin.html', services=services, deposits=deposits, current_user=current_user, usd_to_syp=USD_TO_SYP)

if __name__ == '__main__':
    app.run(debug=True, port=5000)