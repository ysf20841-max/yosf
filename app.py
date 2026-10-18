import os
from datetime import timedelta
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'owj_media_ultra_secret_key_2026'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'nexus_smm.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
USD_TO_SYP = 150.0

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    sub_category = db.Column(db.String(100), nullable=True)
    category_image_url = db.Column(db.String(500), nullable=True)
    sub_category_image_url = db.Column(db.String(500), nullable=True)
    service_image_url = db.Column(db.String(500), nullable=True)
    price_usd = db.Column(db.Float, nullable=False, default=0.0)
    price_syp = db.Column(db.Float, nullable=False, default=0.0)
    service_type = db.Column(db.String(20), default='game')
    input_label = db.Column(db.String(100), default='معرّف الحساب (ID)')
    min_quantity = db.Column(db.Integer, default=1)
    max_quantity = db.Column(db.Integer, default=10000)
    delivery_time = db.Column(db.String(100), default='فوري ⚡')
    provider_api_url = db.Column(db.String(300), nullable=True)
    provider_api_key = db.Column(db.String(300), nullable=True)
    provider_service_id = db.Column(db.String(50), nullable=True)
    is_available = db.Column(db.Boolean, default=True)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class AccountItem(db.Model):
    __tablename__ = 'account_items'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    price_usd = db.Column(db.Float, nullable=False, default=0.0)
    secret_details = db.Column(db.Text, nullable=False)
    is_sold = db.Column(db.Boolean, default=False)
    buyer_username = db.Column(db.String(100), nullable=True)

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    qr_image_url = db.Column(db.String(500), nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance_usd = db.Column(db.Float, default=0.0)
    balance_syp = db.Column(db.Float, default=0.0)
    role = db.Column(db.String(20), default='user') # 'user', 'merchant' (تاجر), 'admin'
    discount_percent = db.Column(db.Float, default=0.0) # نسبة الخصم المئوية للتاجر

class DepositRequest(db.Model):
    __tablename__ = 'deposit_requests'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    amount_usd = db.Column(db.Float, nullable=False, default=0.0)
    transaction_id = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(50), default='pending')

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    service_name = db.Column(db.String(150), nullable=False)
    target_input = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_usd = db.Column(db.Float, nullable=False)
    order_type = db.Column(db.String(20), default='game')
    status = db.Column(db.String(100), default='قيد المراجعة والتنفيذ اليدوي')

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        db.session.add(User(username='admin', password='123456', balance_usd=100.0, role='admin'))
        db.session.commit()

@app.context_processor
def inject_global_data():
    current_user = None
    if session.get('user'):
        current_user = User.query.filter_by(username=session['user']).first()
    active_notifications = Notification.query.filter_by(is_active=True).all()
    return dict(current_user=current_user, active_notifications=active_notifications)

@app.route('/')
def index():
    services = Service.query.all()
    categories = {}
    for s in services:
        if s.category not in categories:
            categories[s.category] = {'count': 0, 'image_url': s.category_image_url}
        categories[s.category]['count'] += 1
        if s.category_image_url and not categories[s.category]['image_url']:
            categories[s.category]['image_url'] = s.category_image_url
    return render_template('index.html', categories=categories, is_admin=(session.get('user') == 'admin'))

@app.route('/category/<cat_name>')
def category_services(cat_name):
    services = Service.query.filter_by(category=cat_name).all()
    current_user = User.query.filter_by(username=session.get('user')).first() if session.get('user') else None
    
    # حساب السعر بعد خصم التتاجر إن وجد
    processed_services = []
    for s in services:
        effective_price = s.price_usd
        if current_user and current_user.role == 'merchant' and current_user.discount_percent > 0:
            effective_price = s.price_usd * (1 - (current_user.discount_percent / 100))
        
        # إنشاء كائن مؤقت أو تعديل السعر للعرض
        s_dict = {
            'id': s.id, 'name': s.name, 'category': s.category,
            'service_image_url': s.service_image_url, 'sub_category_image_url': s.sub_category_image_url,
            'category_image_url': s.category_image_url, 'price_usd': effective_price,
            'price_syp': effective_price * USD_TO_SYP, 'original_price': s.price_usd,
            'service_type': s.service_type, 'input_label': s.input_label,
            'min_quantity': s.min_quantity, 'max_quantity': s.max_quantity,
            'delivery_time': s.delivery_time, 'is_available': s.is_available
        }
        processed_services.append(s_dict)

    return render_template('category_services.html', category_name=cat_name, services=processed_services)

@app.route('/order', methods=['POST'])
def place_order():
    if 'user' not in session: return redirect(url_for('login'))
    service_id = request.form.get('service_id')
    target_input = request.form.get('target_input')
    quantity = int(request.form.get('quantity') or 1)
    
    service = Service.query.get(service_id)
    user = User.query.filter_by(username=session['user']).first()
    
    if service and user:
        base_price = service.price_usd
        if user.role == 'merchant' and user.discount_percent > 0:
            base_price = service.price_usd * (1 - (user.discount_percent / 100))

        total_price = (base_price / 1000) * quantity if service.service_type == 'api' else base_price * quantity
        
        if user.balance_usd >= total_price:
            user.balance_usd -= total_price
            user.balance_syp = user.balance_usd * USD_TO_SYP
            
            if service.service_type == 'api' and service.provider_api_url:
                order_status = 'تم إرسالها تلقائياً للمزود'
                try:
                    payload = {'key': service.provider_api_key, 'action': 'add', 'service': service.provider_service_id, 'link': target_input, 'quantity': quantity}
                    res = requests.post(service.provider_api_url, data=payload, timeout=10).json()
                    if 'order' in res: order_status = f"مقبول آلياً (رقم: {res['order']})"
                except Exception:
                    order_status = 'خطأ اتصال بـ API المزود'
            else:
                order_status = 'قيد المراجعة والتنفيذ اليدوي'

            db.session.add(Order(username=user.username, service_name=service.name, target_input=target_input, quantity=quantity, total_usd=total_price, order_type=service.service_type, status=order_status))
            db.session.commit()
            flash('تم إرسال طلبك بنجاح! 🚀', 'success')
        else:
            flash('رصيد المحفظة غير كافٍ لإتمام الطلب.', 'error')
    return redirect(url_for('my_orders'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if session.get('user') != 'admin': return redirect(url_for('login'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_service':
            s_type = request.form.get('service_type', 'game')
            db.session.add(Service(
                name=request.form.get('name'),
                category=request.form.get('category'),
                sub_category=request.form.get('sub_category') or None,
                category_image_url=request.form.get('category_image_url'),
                sub_category_image_url=request.form.get('sub_category_image_url'),
                service_image_url=request.form.get('service_image_url'),
                price_usd=float(request.form.get('price_usd') or 0),
                price_syp=float(request.form.get('price_usd') or 0) * USD_TO_SYP,
                service_type=s_type,
                input_label='معرّف الحساب (ID)' if s_type == 'game' else 'الرابط / اسم الحساب',
                min_quantity=int(request.form.get('min_quantity') or 1),
                max_quantity=int(request.form.get('max_quantity') or 10000),
                delivery_time=request.form.get('delivery_time') or 'فوري ⚡',
                provider_api_url=request.form.get('provider_api_url'),
                provider_api_key=request.form.get('provider_api_key'),
                provider_service_id=request.form.get('provider_service_id'),
                is_available=True if request.form.get('is_available') == 'true' else False
            ))
            db.session.commit()
        elif action == 'create_merchant':
            m_username = request.form.get('username').strip()
            m_password = request.form.get('password').strip()
            discount = float(request.form.get('discount_percent') or 0)
            gift_amount = float(request.form.get('gift_amount') or 0)
            
            existing = User.query.filter_by(username=m_username).first()
            if existing:
                existing.role = 'merchant'
                existing.discount_percent = discount
                existing.balance_usd += gift_amount
                existing.balance_syp = existing.balance_usd * USD_TO_SYP
                flash(f'تم تحديث حساب {m_username} إلى تاجر بنجاح مع خصم {discount}% وهدية ${gift_amount}!', 'success')
            else:
                new_m = User(username=m_username, password=m_password, role='merchant', discount_percent=discount, balance_usd=gift_amount, balance_syp=gift_amount * USD_TO_SYP)
                db.session.add(new_m)
                flash(f'تم إنشاء حساب تاجر جديد لـ {م_username if "م_username" in locals() else m_username} مع خصم {discount}% وهدية ${gift_amount}!', 'success')
            db.session.commit()
        elif action == 'delete_service':
            Service.query.filter_by(id=request.form.get('service_id')).delete()
            db.session.commit()
        elif action == 'delete_category':
            Service.query.filter_by(category=request.form.get('category_name')).delete()
            db.session.commit()
        elif action == 'complete_manual_order':
            ord_id = request.form.get('order_id')
            o = Order.query.get(ord_id)
            if o:
                o.status = 'تم التنفيذ بنجاح ✓'
                db.session.commit()
        elif action == 'refund_or_add_balance':
            target_username = request.form.get('username').strip()
            amount = float(request.form.get('amount_usd') or 0)
            u = User.query.filter_by(username=target_username).first()
            if u and amount != 0:
                u.balance_usd += amount
                u.balance_syp = u.balance_usd * USD_TO_SYP
                db.session.commit()
                flash(f'تم تعديل رصيد المستخدم {target_username} بمقدار ${amount} بنجاح!', 'success')
            else:
                flash('المستخدم غير موجود أو المبلغ غير صحيح.', 'error')
        elif action == 'add_account_item':
            db.session.add(AccountItem(
                title=request.form.get('title'),
                description=request.form.get('description'),
                image_url=request.form.get('image_url'),
                price_usd=float(request.form.get('price_usd') or 0),
                secret_details=request.form.get('secret_details'),
                is_sold=False
            ))
            db.session.commit()
        elif action == 'delete_account_item':
            AccountItem.query.filter_by(id=request.form.get('account_id')).delete()
            db.session.commit()
        elif action == 'add_payment_method':
            db.session.add(PaymentMethod(title=request.form.get('title'), instructions=request.form.get('instructions'), qr_image_url=request.form.get('qr_image_url')))
            db.session.commit()
        elif action == 'delete_payment_method':
            PaymentMethod.query.filter_by(id=request.form.get('payment_method_id')).delete()
            db.session.commit()
        elif action == 'add_notification':
            db.session.add(Notification(title=request.form.get('title'), message=request.form.get('message'), is_active=True))
            db.session.commit()
        elif action == 'delete_notification':
            Notification.query.filter_by(id=request.form.get('notification_id')).delete()
            db.session.commit()
        elif action == 'approve_deposit':
            dep = DepositRequest.query.get(request.form.get('deposit_id'))
            if dep and dep.status == 'pending':
                dep.status = 'approved'
                u = User.query.filter_by(username=dep.username).first()
                if u:
                    u.balance_usd += dep.amount_usd
                    u.balance_syp = u.balance_usd * USD_TO_SYP
                db.session.commit()
        return redirect(url_for('admin_panel'))
        
    services = Service.query.all()
    categories = list(set([s.category for s in services]))
    deposits = DepositRequest.query.all()
    notifications = Notification.query.all()
    payment_methods = PaymentMethod.query.all()
    accounts = AccountItem.query.all()
    merchants = User.query.filter_by(role='merchant').all()
    manual_orders = Order.query.filter_by(order_type='game').order_by(Order.id.desc()).all()
    return render_template('admin.html', services=services, categories=categories, deposits=deposits, notifications=notifications, payment_methods=payment_methods, accounts=accounts, merchants=merchants, manual_orders=manual_orders)

@app.route('/accounts')
def accounts_store():
    accounts = AccountItem.query.filter_by(is_sold=False).all()
    my_purchased = []
    if session.get('user'):
        my_purchased = AccountItem.query.filter_by(buyer_username=session['user'], is_sold=True).all()
    return render_template('accounts.html', accounts=accounts, my_purchased=my_purchased)

@app.route('/buy_account/<int:acc_id>', methods=['POST'])
def buy_account(acc_id):
    if 'user' not in session: return redirect(url_for('login'))
    acc = AccountItem.query.get(acc_id)
    user = User.query.filter_by(username=session['user']).first()
    if acc and not acc.is_sold and user and user.balance_usd >= acc.price_usd:
        user.balance_usd -= acc.price_usd
        user.balance_syp = user.balance_usd * USD_TO_SYP
        acc.is_sold = True
        acc.buyer_username = user.username
        db.session.commit()
    return redirect(url_for('accounts_store'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        un = request.form.get('username').strip()
        pw = request.form.get('password').strip()
        user = User.query.filter_by(username=un, password=pw).first()
        if user:
            session.permanent = True
            session['user'] = user.username
            if user.role == 'merchant':
                flash(f'أهلاً بك يا شريكنا التاجر المميز {user.username}! 🌟 تم تطبيق خصم حصري بنسبة {user.discount_percent}% على كافة خدمات المنصة.', 'success')
            else:
                flash(f'مرحباً بك مجدداً {user.username} في أوج ميديا ⚡', 'success')
            return redirect(url_for('index'))
        error = 'بيانات الدخول غير صحيحة'
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        un = request.form.get('username').strip()
        pw = request.form.get('password').strip()
        if User.query.filter_by(username=un).first():
            error = 'اسم المستخدم موجود مسبقاً'
        else:
            db.session.add(User(username=un, password=pw, role='user'))
            db.session.commit()
            session.permanent = True
            session['user'] = un
            flash('تم إنشاء حسابك بنجاح! أهلاً بك في أوج ميديا 🚀', 'success')
            return redirect(url_for('index'))
    return render_template('register.html', error=error)

@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        amt = float(request.form.get('amount_usd') or 0)
        tx_id = request.form.get('transaction_id')
        if amt > 0 and tx_id:
            db.session.add(DepositRequest(username=session['user'], amount_usd=amt, transaction_id=tx_id, status='pending'))
            db.session.commit()
        return redirect(url_for('deposit'))
    return render_template('deposit.html', deposits=DepositRequest.query.filter_by(username=session['user']).all(), payment_methods=PaymentMethod.query.all())

@app.route('/my_orders')
def my_orders():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('my_orders.html', orders=Order.query.filter_by(username=session['user']).order_by(Order.id.desc()).all())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)