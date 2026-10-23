import os
import csv
import io
import random
from datetime import timedelta
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, make_response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = 'owj_media_ultra_secure_key_2026'

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
    delivery_time = db.Column(db.String(100), default='فوري')
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
    account_number = db.Column(db.String(150), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    qr_image_url = db.Column(db.String(500), nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(150), nullable=True)
    balance_usd = db.Column(db.Float, default=0.0)
    balance_syp = db.Column(db.Float, default=0.0)
    role = db.Column(db.String(20), default='user')
    discount_percent = db.Column(db.Float, default=0.0)
    email = db.Column(db.String(150), nullable=True)
    phone_syp = db.Column(db.String(50), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_status = db.Column(db.String(30), default='none')
    verification_code = db.Column(db.String(10), nullable=True)
    pending_notice = db.Column(db.Text, nullable=True)

class Agent(db.Model):
    __tablename__ = 'agents'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)

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
    admin_user = User.query.filter_by(username='yosf2008').first()
    if not admin_user:
        db.session.add(User(username='yosf2008', password='2008123rrnny', full_name='يوسف أغا', balance_usd=500.0, role='admin', is_verified=True))
        db.session.commit()
    else:
        admin_user.role = 'admin'
        admin_user.full_name = 'يوسف أغا'
        db.session.commit()

@app.context_processor
def inject_global_data():
    current_user = None
    if session.get('user'):
        try:
            current_user = User.query.filter_by(username=session.get('user')).first()
            if current_user and current_user.pending_notice:
                flash(current_user.pending_notice, 'success')
                current_user.pending_notice = None
                db.session.commit()
        except Exception:
            current_user = None
    return dict(current_user=current_user)

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
    return render_template('index.html', categories=categories, is_admin=(session.get('user') == 'yosf2008'))

@app.route('/category/<cat_name>')
def category_services(cat_name):
    services = Service.query.filter_by(category=cat_name).all()
    current_user = User.query.filter_by(username=session.get('user')).first() if session.get('user') else None
    
    processed_services = []
    for s in services:
        effective_price = s.price_usd
        if current_user and current_user.role == 'merchant' and current_user.discount_percent > 0:
            effective_price = s.price_usd * (1 - (current_user.discount_percent / 100))
        
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

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session: return redirect(url_for('login'))
    user = User.query.filter_by(username=session['user']).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            user.full_name = request.form.get('full_name')
            new_pass = request.form.get('new_password')
            if new_pass:
                user.password = new_pass
            db.session.commit()
            flash('تم تحديث بيانات الحساب بنجاح', 'success')
        elif action == 'send_code':
            user.full_name = request.form.get('full_name')
            user.email = request.form.get('email')
            user.phone_syp = request.form.get('phone_syp')
            code = str(random.randint(100000, 999999))
            user.verification_code = code
            db.session.commit()
            flash(f'[رسالة رسمية من أوج ميديا] رمز التحقق الخاص بك هو: {code}. يرجى إدخاله في الحقل المخصص.', 'success')
        elif action == 'verify_account':
            entered_code = request.form.get('code')
            if entered_code and entered_code == user.verification_code:
                user.verification_status = 'pending'
                db.session.commit()
                flash('تم إرسال طلب التوثيق للإدارة بنجاح', 'success')
            else:
                flash('رمز التحقق غير صحيح', 'error')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/agents')
def agents():
    all_agents = Agent.query.all()
    return render_template('agents.html', agents=all_agents)

@app.route('/about')
def about():
    return render_template('about.html')

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
            
            order_status = 'قيد المراجعة والتنفيذ اليدوي'
            if service.service_type == 'api' and service.provider_api_url:
                try:
                    payload = {'key': service.provider_api_key, 'action': 'add', 'service': service.provider_service_id, 'link': target_input, 'quantity': quantity}
                    res = requests.post(service.provider_api_url, data=payload, timeout=10).json()
                    if 'order' in res: 
                        order_status = f"مقبول آلياً (رقم: {res['order']})"
                    else:
                        order_status = 'تم الإرسال للمزود'
                except Exception:
                    order_status = 'قيد المعالجة اليدوية'

            db.session.add(Order(username=user.username, service_name=service.name, target_input=target_input, quantity=quantity, total_usd=total_price, order_type=service.service_type, status=order_status))
            db.session.commit()
            flash('تم إرسال طلبك بنجاح', 'success')
        else:
            flash('رصيد المحفظة غير كافٍ لإتمام الطلب', 'error')
    return redirect(url_for('my_orders'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    current_admin = User.query.filter_by(username=session.get('user')).first()
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'send_balance_by_id':
            target_id = int(request.form.get('target_id') or 0)
            amount = float(request.form.get('amount') or 0)
            notice_msg = request.form.get('notice_msg') or 'تمت إضافة رصيد لحسابك'
            target_user = User.query.get(target_id)
            if target_user and amount != 0:
                target_user.balance_usd += amount
                target_user.balance_syp = target_user.balance_usd * USD_TO_SYP
                target_user.pending_notice = f"إشعار رصيد: {notice_msg} (+${amount})"
                db.session.commit()
                flash('تم إرسال الرصيد بنجاح', 'success')
            else:
                flash('معرّف المستخدم غير موجود أو المبلغ غير صحيح', 'error')
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
                flash('تم تحديث حساب التاجر بنجاح', 'success')
            else:
                new_m = User(username=m_username, password=m_password, full_name=m_username, role='merchant', discount_percent=discount, balance_usd=gift_amount, balance_syp=gift_amount * USD_TO_SYP)
                db.session.add(new_m)
                flash('تم إنشاء حساب تاجر جديد بنجاح', 'success')
            db.session.commit()
        elif action == 'add_service':
            db.session.add(Service(
                name=request.form.get('name'),
                category=request.form.get('category'),
                sub_category=request.form.get('sub_category') or None,
                category_image_url=request.form.get('category_image_url') or None,
                service_image_url=request.form.get('service_image_url') or None,
                price_usd=float(request.form.get('price_usd') or 0),
                price_syp=float(request.form.get('price_usd') or 0) * USD_TO_SYP,
                service_type=request.form.get('service_type', 'game'),
                input_label=request.form.get('input_label') or 'معرّف الحساب (ID)',
                min_quantity=int(request.form.get('min_quantity') or 1),
                max_quantity=int(request.form.get('max_quantity') or 10000),
                delivery_time=request.form.get('delivery_time') or 'فوري',
                provider_api_url=request.form.get('provider_api_url'),
                provider_api_key=request.form.get('provider_api_key'),
                provider_service_id=request.form.get('provider_service_id'),
                is_available=True
            ))
            db.session.commit()
            flash('تم إضافة الخدمة بنجاح', 'success')
        elif action == 'approve_verification':
            u_id = request.form.get('user_id')
            target_u = User.query.get(u_id)
            if target_u:
                target_u.is_verified = True
                target_u.verification_status = 'verified'
                db.session.commit()
                flash('تم توثيق الحساب بنجاح', 'success')
        elif action == 'reject_verification':
            u_id = request.form.get('user_id')
            target_u = User.query.get(u_id)
            if target_u:
                target_u.verification_status = 'none'
                db.session.commit()
                flash('تم رفض طلب التوثيق', 'error')
        elif action == 'add_agent':
            db.session.add(Agent(name=request.form.get('name'), city=request.form.get('city'), phone=request.form.get('phone'), details=request.form.get('details')))
            db.session.commit()
            flash('تم إضافة الوكيل بنجاح', 'success')
        elif action == 'delete_agent':
            Agent.query.filter_by(id=request.form.get('agent_id')).delete()
            db.session.commit()
            flash('تم حذف الوكيل بنجاح', 'success')
        elif action == 'delete_service':
            Service.query.filter_by(id=request.form.get('service_id')).delete()
            db.session.commit()
            flash('تم حذف الخدمة بنجاح', 'success')
        elif action == 'delete_category':
            cat_to_del = request.form.get('category_name')
            Service.query.filter_by(category=cat_to_del).delete()
            db.session.commit()
            flash('تم حذف القسم بنجاح', 'success')
        elif action == 'add_payment_method':
            db.session.add(PaymentMethod(title=request.form.get('title'), account_number=request.form.get('account_number'), qr_image_url=request.form.get('qr_image_url'), instructions=request.form.get('instructions')))
            db.session.commit()
            flash('تم إضافة طريقة الدفع بنجاح', 'success')
        elif action == 'add_notification':
            db.session.add(Notification(title=request.form.get('title'), message=request.form.get('message')))
            db.session.commit()
            flash('تم نشر الإشعار بنجاح', 'success')
        elif action == 'complete_manual_order':
            o = Order.query.get(request.form.get('order_id'))
            if o:
                o.status = 'تم التنفيذ بنجاح'
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
    pending_verifications = User.query.filter_by(verification_status='pending').all()
    agents = Agent.query.all()
    all_users = User.query.all()
    merchants = User.query.filter_by(role='merchant').all()
    manual_orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin.html', services=services, categories=categories, deposits=deposits, pending_verifications=pending_verifications, agents=agents, all_users=all_users, merchants=merchants, manual_orders=manual_orders)

@app.route('/accounts')
def accounts_store():
    return render_template('accounts.html')

@app.route('/ai_bot')
def ai_bot():
    current_user_name = "زريق" # قيمة افتراضية للضيف
    if session.get('user'):
        u = User.query.filter_by(username=session.get('user')).first()
        if u and u.full_name:
            current_user_name = u.full_name
        elif u:
            current_user_name = u.username
    return render_template('ai_bot.html', user_name=current_user_name)

@app.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    data = request.get_json() or {}
    user_msg = data.get('message', '').strip()
    user_msg_lower = user_msg.lower()
    
    # جلب اسم المستخدم الحالي للترحيب به
    current_user_name = "صديقي"
    if session.get('user'):
        u = User.query.filter_by(username=session.get('user')).first()
        if u and u.full_name:
            current_user_name = u.full_name
        elif u:
            current_user_name = u.username

    action_button = None
    response_msg = ""
    
    # التحقق من الأسئلة المختلفة والرد عليها بدقة واحترافية
    if any(k in user_msg_lower for k in ['من صنعك', 'صانعك', 'مطورك', 'مين صنعو', 'المبرمج', 'يوسف أغا', 'مالك', 'من أنت']):
        response_msg = f"أهلاً بك يا {current_user_name}! تم تصميم وتطوير منصة **أوج ميديا (OWJ Media)** بكل احترافية بواسطة المبرمج والمدير الإبداعي **يوسف أغا** لتكون المنصة الأولى للخدمات الرقمية وشحن الألعاب."
    elif any(k in user_msg_lower for k in ['تواصل', 'رقم', 'اتصال', 'دعم', 'فريق', 'مراسلة', 'واتساب']):
        response_msg = f"يسعدنا تواصلك معنا يا {current_user_name}! يمكنك التواصل مباشرة مع المدير **يوسف أغا** عبر رقم الواتساب الرسمي: **+963952169815** أو عبر قنوات الدعم داخل المنصة."
    elif any(k in user_msg_lower for k in ['شحن', 'رصيد', 'دفع', 'شام كاش', 'سيريتل كاش', 'محفظة', 'كيف أشحن']):
        response_msg = f"عملية شحن الرصيد يا {current_user_name} سهلة جداً: انتقل إلى صفحة (شحن المحفظة)، انسخ رقم الحساب الخاص بطريقة الدفع (مثل شام كاش)، ثم أدخل مبلغ التحويل ورقم الإيصال ليتم الاعتماد فوراً."
    elif any(k in user_msg_lower for k in ['خدمات', 'سوشيال', 'ألعاب', 'ببجي', 'انستغرام', 'تيك توك', 'اسعار', 'سعر', 'ميزات', 'ماذا يوجد', 'قسم']):
        response_msg = f"نقدم في **أوج ميديا** أرقى خدمات السوشيال ميديا وشحن الألعاب بأسعار منافسة وسرعة فائقة في التنفيذ، مع خصومات حصرية لحسابات التجار. يمكنك تصفح جميع الأقسام والخدمات المتوفرة مباشرة عبر الزر أدناه:"
        action_button = {"text": "اضغط هنا لعرض الخدمات والانتقال للمتجر", "url": "/#"}
    elif any(k in user_msg_lower for k in ['كيف حالك', 'مرحبا', 'اهلاً', 'السلام عليكم']):
        response_msg = f"وعليكم السلام ورحمة الله يا {current_user_name}! أنا بخير ولله الحمد، ومستعد تماماً لمساعدتك في أي استفسار يخص منصة أوج ميديا، الخدمات، أو حتى الأسئلة البرمجية والتقنية. بماذا يمكنني أن أخدمك اليوم؟"
    else:
        # رد ذكي وعام وشامل لأي استفسار آخر يكتبه المستخدم
        response_msg = f"أهلاً بك يا {current_user_name}. بصفتي مساعدك الذكي في منصة أوج ميديا، أستطيع مساعدتك في كل ما يتعلق بإدارة حسابك، شحن الرصيد، معرفة تفاصيل الخدمات، أو الإجابة على استفساراتك التقنية والتسويقية. تفضل بطرح سؤالك وسأجيبك فوراً بكل تفصيل!"

    return {'reply': response_msg, 'action_button': action_button}
    
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
            db.session.add(User(username=un, password=pw, full_name=un, role='user'))
            db.session.commit()
            session.permanent = True
            session['user'] = un
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