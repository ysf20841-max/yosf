import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-deployment')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///owj_media.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), default='')
    email = db.Column(db.String(160), default='')
    phone = db.Column(db.String(40), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')
    balance_usd = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    @property
    def is_authenticated(self): return True
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    image_url = db.Column(db.String(500), default='')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    price = db.Column(db.Float, default=1.0) # price per 1000 for SMM, fixed price for manual
    price_per_1000 = db.Column(db.Float, default=1.0)
    min_quantity = db.Column(db.Integer, default=10)
    max_quantity = db.Column(db.Integer, default=10000)
    input_label = db.Column(db.String(180), default='الرابط أو الآيدي')
    service_type = db.Column(db.String(20), default='manual')
    image_url = db.Column(db.String(500), default='')
    description = db.Column(db.Text, default='')
    is_available = db.Column(db.Boolean, default=True)
    category = db.relationship('Category', backref=db.backref('services', lazy=True))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=True)
    service_name = db.Column(db.String(160), default='')
    link = db.Column(db.String(1000), default='')
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(40), default='قيد المراجعة')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='orders')
    service = db.relationship('Service')

class VerificationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(120), default='')
    email = db.Column(db.String(160), default='')
    phone = db.Column(db.String(40), default='')
    status = db.Column(db.String(20), default='pending')
    user = db.relationship('User')

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), default='')
    phone = db.Column(db.String(60), default='')
    details = db.Column(db.Text, default='')

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    qr_code_url = db.Column(db.String(500), default='')
    account_number = db.Column(db.String(180), default='')
    instructions = db.Column(db.Text, default='')

class DepositRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, default=0)
    proof = db.Column(db.String(500), default='')
    status = db.Column(db.String(30), default='قيد المراجعة')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')

@app.context_processor
def inject_globals():
    user = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
    return {'current_user': user, 'site_name': 'أوج ميديا'}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('سجّل الدخول أولاً للمتابعة.', 'error')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
        if not user or user.role != 'admin': abort(403)
        return fn(*args, **kwargs)
    return wrapped

def current_user():
    return db.session.get(User, session.get('user_id')) if session.get('user_id') else None

@app.route('/')
def index():
    categories = Category.query.order_by(Category.id).all()
    services = Service.query.order_by(Service.id.desc()).limit(9).all()
    return render_template('index.html', categories=categories, services=services)

@app.route('/accounts')
def accounts():
    services = Service.query.order_by(Service.id.desc()).all()
    return render_template('accounts.html', services=services)

@app.route('/category/<int:category_id>')
def category_services(category_id):
    category = Category.query.get_or_404(category_id)
    services = Service.query.filter_by(category_id=category_id).order_by(Service.id.desc()).all()
    return render_template('category_services.html', category=category, services=services)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username','').strip()).first()
        if user and user.check_password(request.form.get('password','')):
            session.clear(); session['user_id'] = user.id
            flash('تم تسجيل الدخول بنجاح.', 'success')
            return redirect(url_for('index'))
        flash('اسم المستخدم أو كلمة المرور غير صحيحة.', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        if len(username) < 3 or len(password) < 8:
            flash('اسم المستخدم 3 أحرف على الأقل وكلمة المرور 8 أحرف على الأقل.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('اسم المستخدم مستخدم بالفعل.', 'error')
        else:
            user = User(username=username, full_name=request.form.get('full_name','').strip(), email=request.form.get('email','').strip(), phone=request.form.get('phone','').strip())
            user.set_password(password); db.session.add(user); db.session.commit()
            session['user_id'] = user.id
            flash('تم إنشاء الحساب بنجاح.', 'success')
            return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    user = current_user()
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name).strip()
        user.email = request.form.get('email', user.email).strip()
        user.phone = request.form.get('phone', user.phone).strip()
        db.session.commit(); flash('تم تحديث بياناتك.', 'success'); return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/my_orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user().id).order_by(Order.id.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/order/<int:service_id>', methods=['POST'])
@login_required
def place_order(service_id):
    service = Service.query.get_or_404(service_id)
    user = current_user()
    if not service.is_available:
        flash('هذه الخدمة غير متوفرة حالياً.', 'error'); return redirect(url_for('category_services', category_id=service.category_id))
    link = request.form.get('link','').strip()
    try: quantity = int(request.form.get('quantity', service.min_quantity or 1))
    except ValueError: quantity = 0
    if not link or quantity < (service.min_quantity or 1) or quantity > (service.max_quantity or 10000):
        flash('تحقق من الرابط والكمية المطلوبة.', 'error'); return redirect(url_for('category_services', category_id=service.category_id))
    total = (service.price_per_1000 * quantity / 1000) if service.service_type == 'smm' else service.price
    if user.balance_usd < total:
        flash('رصيدك غير كافٍ. يرجى شحن المحفظة أولاً.', 'error'); return redirect(url_for('deposit'))
    user.balance_usd -= total
    order = Order(user_id=user.id, service_id=service.id, service_name=service.name, link=link, quantity=quantity, total_price=total)
    db.session.add(order); db.session.commit()
    flash('تم استلام طلبك بنجاح.', 'success'); return redirect(url_for('my_orders'))

@app.route('/deposit', methods=['GET','POST'])
def deposit():
    payments = PaymentMethod.query.order_by(PaymentMethod.id.desc()).all()
    if request.method == 'POST':
        if not session.get('user_id'): return redirect(url_for('login'))
        try: amount = float(request.form.get('amount', '0'))
        except ValueError: amount = 0
        if amount <= 0:
            flash('أدخل مبلغاً صحيحاً.', 'error')
        else:
            db.session.add(DepositRequest(user_id=current_user().id, amount=amount, proof=request.form.get('proof','').strip()))
            db.session.commit(); flash('تم إرسال طلب الشحن للمراجعة.', 'success'); return redirect(url_for('deposit'))
    return render_template('deposit.html', payments=payments)

@app.route('/agents')
def agents(): return render_template('agents.html', agents=Agent.query.order_by(Agent.id.desc()).all())
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/ai_bot')
@login_required
def ai_bot(): return render_template('ai_bot.html', user_name=current_user().full_name or current_user().username)

@app.route('/api/ai_chat', methods=['POST'])
@login_required
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get('message','')).strip()[:1000]
    if not message: return jsonify(reply='اكتب سؤالك أولاً.'), 400
    m = message.lower()
    if any(x in m for x in ['شحن','رصيد','دفع','تحويل']):
        reply = 'لشحن رصيدك افتح قسم «الشحن» من الشريط السفلي، واختر طريقة الدفع المتاحة. إذا أرسلت طلب شحن فسيظهر للإدارة للمراجعة.'
    elif any(x in m for x in ['طلباتي','طلب','الطلبات']):
        reply = 'يمكنك متابعة طلباتك من قسم «طلباتي» في الشريط السفلي. تظهر حالة كل طلب وتكلفته.'
    elif any(x in m for x in ['خدمة','سعر','متجر','انستغرام','تيك','تيك توك']):
        reply = 'تصفح المتجر الرقمي لاختيار الخدمة. ستجد السعر وحالة التوفر، ويمكنك فتح القسم لمعرفة التفاصيل.'
    elif any(x in m for x in ['مرحبا','السلام','اهلا','أهلا']):
        reply = 'أهلاً وسهلاً بك في أوج ميديا 👋 كيف أقدر أساعدك؟ اسألني عن الخدمات أو الطلبات أو الشحن.'
    else:
        reply = 'أنا مساعد أوج ميديا التجريبي. أستطيع إرشادك إلى الخدمات والطلبات والشحن. للمساعدة الخاصة، تواصل مع فريق الدعم من خلال الوكلاء المعتمدين.'
    return jsonify(reply=reply)

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', orders=Order.query.order_by(Order.id.desc()).all(), verification_requests=VerificationRequest.query.filter_by(status='pending').all(), categories=Category.query.all(), services=Service.query.all(), deposits=DepositRequest.query.order_by(DepositRequest.id.desc()).all())

@app.route('/admin/complete_order/<int:order_id>', methods=['POST'])
@admin_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id); order.status='مكتمل'; db.session.commit(); flash('تم تحديث حالة الطلب.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/handle_verification/<int:req_id>', methods=['POST'])
@admin_required
def handle_verification(req_id):
    req = VerificationRequest.query.get_or_404(req_id); action=request.form.get('action')
    if action == 'approve': req.user.is_verified=True; req.status='approved'
    else: req.status='rejected'
    db.session.commit(); flash('تم تحديث طلب التوثيق.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/send_balance', methods=['POST'])
@admin_required
def send_balance():
    user=User.query.get(request.form.get('user_id',type=int)); amount=request.form.get('amount',type=float)
    if not user or amount is None or amount <= 0: flash('تحقق من ID والمبلغ.', 'error')
    else: user.balance_usd += amount; db.session.commit(); flash('تم إرسال الرصيد.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add_merchant', methods=['POST'])
@admin_required
def add_merchant():
    username=request.form.get('username','').strip(); password=request.form.get('password','')
    if not username or len(password)<8 or User.query.filter_by(username=username).first(): flash('تعذر إنشاء التاجر: تحقق من البيانات وكلمة المرور (8 أحرف على الأقل).', 'error')
    else:
        user=User(username=username, role='merchant', balance_usd=max(0, request.form.get('bonus',type=float) or 0)); user.set_password(password); db.session.add(user); db.session.commit(); flash('تم إنشاء حساب التاجر.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/add_payment', methods=['POST'])
@admin_required
def add_payment():
    db.session.add(PaymentMethod(name=request.form.get('name','').strip(), qr_code_url=request.form.get('qr_code_url','').strip(), account_number=request.form.get('account_number','').strip(), instructions=request.form.get('instructions','').strip())); db.session.commit(); flash('تمت إضافة طريقة الدفع.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/add_agent', methods=['POST'])
@admin_required
def add_agent():
    db.session.add(Agent(name=request.form.get('name','').strip(), city=request.form.get('city','').strip(), phone=request.form.get('phone','').strip(), details=request.form.get('address','').strip())); db.session.commit(); flash('تمت إضافة الوكيل.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/add_service', methods=['POST'])
@admin_required
def add_service():
    name=request.form.get('name','').strip(); category_name=request.form.get('category_name','').strip()
    if not name or not category_name: flash('أدخل اسم الخدمة والقسم.', 'error'); return redirect(url_for('admin'))
    cat=Category.query.filter_by(name=category_name).first()
    if not cat: cat=Category(name=category_name, image_url=request.form.get('category_image_url','').strip()); db.session.add(cat); db.session.flush()
    price=request.form.get('price_per_1000',type=float) or 0
    typ=request.form.get('service_type','manual')
    service=Service(name=name, category_id=cat.id, price=price, price_per_1000=price, min_quantity=request.form.get('min_quantity',type=int) or 1, max_quantity=request.form.get('max_quantity',type=int) or 10000, input_label=request.form.get('input_label','الرابط أو الآيدي').strip(), service_type=typ, image_url=request.form.get('image_url','').strip(), description=request.form.get('description','').strip())
    db.session.add(service); db.session.commit(); flash('تمت إضافة الخدمة.', 'success'); return redirect(url_for('admin'))

@app.route('/admin/delete_category', methods=['POST'])
@admin_required
def delete_category():
    cat=Category.query.get(request.form.get('category_id',type=int))
    if cat:
        for s in list(cat.services): db.session.delete(s)
        db.session.delete(cat); db.session.commit(); flash('تم حذف القسم وخدماته.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/delete_service', methods=['POST'])
@admin_required
def delete_service():
    service=Service.query.get(request.form.get('service_id',type=int))
    if service: db.session.delete(service); db.session.commit(); flash('تم حذف الخدمة.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/export_backup')
@admin_required
def export_backup():
    from flask import Response
    import csv, io
    out=io.StringIO(); writer=csv.writer(out); writer.writerow(['id','username','email','balance_usd','role'])
    for u in User.query.all(): writer.writerow([u.id,u.username,u.email,u.balance_usd,u.role])
    return Response('\ufeff'+out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=owj_users_backup.csv'})

@app.route('/admin/toggle_service/<int:service_id>', methods=['POST'])
@admin_required
def toggle_service(service_id):
    service=Service.query.get_or_404(service_id); service.is_available=not service.is_available; db.session.commit(); flash('تم تحديث توفر الخدمة.', 'success'); return redirect(url_for('admin'))

with app.app_context():
    db.create_all()
    # Seed minimal sample data and an admin only when the database is empty.
    if not User.query.filter_by(role='admin').first():
        admin_user=User(username=os.environ.get('OWJ_ADMIN_USER','admin'), full_name='مدير أوج ميديا', role='admin', balance_usd=0)
        admin_user.set_password(os.environ.get('OWJ_ADMIN_PASSWORD','12345678'))
        db.session.add(admin_user)
    if Category.query.count() == 0:
        c1=Category(name='خدمات التواصل الاجتماعي'); c2=Category(name='شحن الألعاب'); db.session.add_all([c1,c2]); db.session.flush()
        db.session.add_all([
            Service(name='متابعون تجريبيون',category_id=c1.id,price=1.5,price_per_1000=1.5,min_quantity=10,max_quantity=10000,input_label='رابط الحساب أو المنشور',service_type='smm',description='خدمة تجريبية، عدّلها من لوحة الإدارة.'),
            Service(name='شحن ألعاب تجريبي',category_id=c2.id,price=2.0,price_per_1000=2.0,min_quantity=1,max_quantity=1,input_label='معرّف اللاعب ID',service_type='manual',description='خدمة تجريبية، عدّلها من لوحة الإدارة.')])
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
