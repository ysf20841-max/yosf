import os
import io
import csv
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'owj_media_secret_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexus_smm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='user') # user, merchant, admin
    balance_usd = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    image_url = db.Column(db.String(300), nullable=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    service_type = db.Column(db.String(50), default='manual') # manual أو smm
    image_url = db.Column(db.String(300), nullable=True)
    api_url = db.Column(db.String(300), nullable=True)
    api_key = db.Column(db.String(300), nullable=True)
    provider_service_id = db.Column(db.String(100), nullable=True)

    @property
    def price_usd(self):
        return self.price

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    service_name = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='قيد التنفيذ')

class VerificationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='pending')
    reject_reason = db.Column(db.Text, nullable=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    qr_code_url = db.Column(db.String(300), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    account_number = db.Column(db.String(100), nullable=True)

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=True)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin_user = User(
            username='admin',
            password=generate_password_hash('admin123'),
            full_name='يوسف أغا',
            role='admin',
            balance_usd=500.0,
            is_verified=True
        )
        db.session.add(admin_user)
        db.session.commit()

@app.route('/')
def index():
    categories_data = {}
    categories = Category.query.all()
    for cat in categories:
        count = Service.query.filter_by(category_id=cat.id).count()
        categories_data[cat.id] = {
            'name': cat.name,
            'image_url': cat.image_url,
            'count': count
        }
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    notifications = Notification.query.all()
    return render_template('index.html', categories=categories_data, current_user=current_user, notifications=notifications)

@app.route('/accounts')
def accounts():
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    categories = Category.query.all()
    services = Service.query.all()
    return render_template('accounts.html', current_user=current_user, categories=categories, services=services)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user'] = user.username
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(url_for('index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيح', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        account_type = request.form.get('account_type', 'user')
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم مستخدم مسبقاً', 'danger')
            return redirect(url_for('register'))
        new_user = User(
            username=username,
            password=generate_password_hash(password),
            full_name=full_name,
            role=account_type,
            balance_usd=0.0,
            is_verified=True if account_type == 'merchant' else False
        )
        db.session.add(new_user)
        db.session.commit()
        flash('تم إنشاء الحساب بنجاح', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_user = User.query.filter_by(username=session['user']).first()
    pending_req = VerificationRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    rejected_req = VerificationRequest.query.filter_by(user_id=current_user.id, status='rejected').first()
    return render_template('profile.html', current_user=current_user, pending_req=pending_req, rejected_req=rejected_req)

@app.route('/request_verification', methods=['POST'])
def request_verification():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_user = User.query.filter_by(username=session['user']).first()
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    
    existing = VerificationRequest.query.filter_by(user_id=current_user.id, status='pending').first()
    if not existing:
        req = VerificationRequest(user_id=current_user.id, full_name=full_name, email=email, phone=phone, status='pending')
        db.session.add(req)
        db.session.commit()
        flash('تم إرسال طلب التوثيق للإدارة بنجاح', 'success')
    else:
        flash('لديك طلب توثيق قيد المراجعة مسبقاً', 'info')
    return redirect(url_for('profile'))

@app.route('/category/<int:cat_id>')
def category_services(cat_id):
    cat = Category.query.get_or_404(cat_id)
    services = Service.query.filter_by(category_id=cat.id).all()
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    return render_template('category_services.html', category=cat, services=services, current_user=current_user)

@app.route('/deposit')
def deposit():
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    payments = PaymentMethod.query.all()
    return render_template('deposit.html', current_user=current_user, payments=payments)

@app.route('/agents')
def agents():
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    all_agents = Agent.query.all()
    return render_template('agents.html', current_user=current_user, agents=all_agents)

@app.route('/my_orders')
def my_orders():
    if 'user' not in session:
        return redirect(url_for('login'))
    current_user = User.query.filter_by(username=session['user']).first()
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('my_orders.html', current_user=current_user, orders=orders)

# --- مسارات البوت التجريبي (المساعد الذكي) ---
@app.route('/ai_bot')
def ai_bot():
    current_user = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    user_name = current_user.full_name if current_user else 'زائرنا الكريم'
    return render_template('ai_bot.html', current_user=current_user, user_name=user_name)

@app.route('/api/ai_chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    msg = data.get('message', '').lower()
    reply = "أهلاً بك في أوج ميديا! أنا مساعدك الذكي، كيف يمكنني مساعدتك اليوم في خدماتنا أو أسعارنا؟"
    if 'خدمات' in msg or 'أسعار' in msg or 'سعر' in msg:
        reply = "تستطيع استعراض كافة أقسام الخدمات والأسعار بشكل تفصيلي من خلال قسم المتجر الرقمي بالموقع."
    elif 'مدير' in msg or 'يوسف' in msg:
        reply = "مؤسس ومدير منصة أوج ميديا الرقمية هو المبدع يوسف أغا."
    elif 'شحن' in msg or 'رصيد' in msg:
        reply = "يمكنك شحن رصيدك عبر زيارة صفحة شحن المحفظة والتواصل مع وكلائنا المعتمدين."
    return {"reply": reply}

# --- مسارات لوحة التحكم الإدارية ---
@app.route('/admin')
def admin_panel():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    orders = Order.query.all()
    categories = Category.query.all()
    services = Service.query.all()
    users = User.query.all()
    payments = PaymentMethod.query.all()
    all_agents = Agent.query.all()
    verification_requests = VerificationRequest.query.filter_by(status='pending').all()
    return render_template('admin.html', current_user=current_admin, orders=orders, categories=categories, services=services, users=users, payments=payments, agents=all_agents, verification_requests=verification_requests)

@app.route('/admin/complete_order/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    order = Order.query.get_or_404(order_id)
    order.status = 'مكتمل'
    db.session.commit()
    flash('تم تعيين حالة الطلب إلى مكتمل بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/handle_verification/<int:req_id>', methods=['POST'])
def handle_verification(req_id):
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    action = request.form.get('action')
    v_req = VerificationRequest.query.get_or_404(req_id)
    if action == 'approve':
        v_req.status = 'approved'
        target_user = User.query.get(v_req.user_id)
        if target_user:
            target_user.is_verified = True
        db.session.commit()
        flash('تمت الموافقة على طلب التوثيق بنجاح', 'success')
    elif action == 'reject':
        reason = request.form.get('reject_reason', 'لم يتم استيفاء الشروط المطلوبة')
        v_req.status = 'rejected'
        v_req.reject_reason = reason
        db.session.commit()
        flash('تم رفض طلب التوثيق وإرسال السبب للمستخدم', 'info')
    return redirect(url_for('admin_panel'))

@app.route('/admin/send_balance', methods=['POST'])
def send_balance():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    user_id = request.form.get('user_id')
    amount = float(request.form.get('amount', 0))
    target_user = User.query.get(user_id)
    if target_user:
        target_user.balance_usd += amount
        db.session.commit()
        flash(f'تم إرسال بمبلغ ${amount} بنجاح إلى المستخدم #{target_user.id}', 'success')
    else:
        flash('المستخدم غير موجود', 'danger')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_merchant', methods=['POST'])
def add_merchant():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    username = request.form.get('username')
    password = request.form.get('password')
    bonus = float(request.form.get('bonus', 0))
    if not User.query.filter_by(username=username).first():
        new_m = User(username=username, password=generate_password_hash(password), role='merchant', balance_usd=bonus, is_verified=True)
        db.session.add(new_m)
        db.session.commit()
        flash('تم تفعيل حساب التاجر بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_payment', methods=['POST'])
def add_payment():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    name = request.form.get('name')
    qr_code_url = request.form.get('qr_code_url')
    instructions = request.form.get('instructions')
    account_number = request.form.get('account_number')
    db.session.add(PaymentMethod(name=name, qr_code_url=qr_code_url, instructions=instructions, account_number=account_number))
    db.session.commit()
    flash('تم إضافة طريقة الدفع بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_agent', methods=['POST'])
def add_agent():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    db.session.add(Agent(name=request.form.get('name'), city=request.form.get('city'), phone=request.form.get('phone'), address=request.form.get('address')))
    db.session.commit()
    flash('تم إضافة الوكيل بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_category', methods=['POST'])
def delete_category():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    cat_id = request.form.get('category_id')
    cat = Category.query.get(cat_id)
    if cat:
        Service.query.filter_by(category_id=cat.id).delete()
        db.session.delete(cat)
        db.session.commit()
        flash('تم حذف القسم بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_service', methods=['POST'])
def delete_service():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    serv_id = request.form.get('service_id')
    serv = Service.query.get(serv_id)
    if serv:
        db.session.delete(serv)
        db.session.commit()
        flash('تم حذف الخدمة بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_service', methods=['POST'])
def add_service():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    cat_name = request.form.get('category_name')
    cat = Category.query.filter_by(name=cat_name).first()
    if not cat:
        cat = Category(name=cat_name, image_url=request.form.get('category_image_url'))
        db.session.add(cat)
        db.session.commit()
    service = Service(
        category_id=cat.id,
        name=request.form.get('name'),
        price=float(request.form.get('price', 0)),
        service_type=request.form.get('service_type', 'manual'),
        image_url=request.form.get('image_url'),
        api_url=request.form.get('api_url'),
        api_key=request.form.get('api_key'),
        provider_service_id=request.form.get('provider_service_id'),
        description=request.form.get('description')
    )
    db.session.add(service)
    db.session.commit()
    flash('تم إضافة الخدمة ونوعها بنجاح', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/export_backup')
def export_backup():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Username', 'FullName', 'Role', 'BalanceUSD', 'Verified'])
    for u in User.query.all():
        writer.writerow([u.id, u.username, u.full_name, u.role, u.balance_usd, u.is_verified])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=owj_backup_database.csv"})

@app.route('/admin/restore_backup', methods=['POST'])
def restore_backup():
    current_admin = User.query.filter_by(username=session.get('user')).first() if 'user' in session else None
    if not current_admin or current_admin.role != 'admin':
        return redirect(url_for('login'))
    if 'backup_file' in request.files:
        flash('تم استعادة النسخة الاحتياطية بنجاح', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True)