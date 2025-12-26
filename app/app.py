from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from config import Config
from datetime import datetime
from utils import export_to_csv, import_csv_to_list
import os, json, boto3, base64
from werkzeug.utils import secure_filename 
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user 
import qrcode 
from io import BytesIO 

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# --- S3 Helper ---
def upload_to_s3(file, bucket_name):
    if not bucket_name: return None
    s3 = boto3.client('s3', aws_access_key_id=app.config['S3_KEY'], aws_secret_access_key=app.config['S3_SECRET'], region_name=app.config['S3_REGION'])
    try:
        filename = secure_filename(file.filename)
        s3.upload_fileobj(file, bucket_name, filename, ExtraArgs={"ContentType": file.content_type})
        return f"https://{bucket_name}.s3.{app.config['S3_REGION']}.amazonaws.com/{filename}"
    except Exception as e:
        print("S3 Upload Error:", e)
        return None

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image_path = db.Column(db.String(255), nullable=True) # S3 URL
    custom_data = db.Column(db.String(500), nullable=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    address = db.Column(db.String(255), nullable=True)
    transactions = db.relationship('Transaction', backref='customer', lazy=True, cascade="all, delete-orphan") 

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False) 
    total_cost = db.Column(db.Float, nullable=False) 
    status = db.Column(db.String(50), default='Cash') 
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True) 

# --- Setup ---
@app.template_filter('currency')
def format_currency(value): return f'₹ {value:,.2f}'

@app.template_filter('from_json')
def from_json_filter(json_data):
    try: return json.loads(json_data)
    except: return {}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

def generate_product_qr(product_id):
    qr_data = f"POS_PRODUCT_{product_id}" 
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

# --- Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', products=Product.query.all(), all_customers=Customer.query.all())

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price', 0.0))
        stock = int(request.form.get('stock', 0))
        image_url = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                image_url = upload_to_s3(file, app.config['S3_BUCKET'])
        
        custom_data = json.dumps({k: request.form.get(f'custom_{k}','') for k in ['supplier', 'location', 'color']})
        new_product = Product(name=name, price=price, stock=stock, image_path=image_url, custom_data=custom_data)
        db.session.add(new_product)
        db.session.commit()
        new_product.custom_data = generate_product_qr(new_product.id)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('product_form.html', title='Add New Product', product=None)

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price', 0.0))
        product.stock = int(request.form.get('stock', 0))
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                image_url = upload_to_s3(file, app.config['S3_BUCKET'])
                if image_url: product.image_path = image_url
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('product_form.html', title='Edit Product', product=product)

@app.route('/products')
@login_required
def products():
    return render_template('products.html', products=Product.query.all(), custom_headers=['supplier', 'location', 'color'])

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    data = request.get_json()
    cart, customer_id, method = data.get('cart', []), data.get('customer_id'), data.get('payment_method')
    total = 0
    try:
        for item in cart:
            p = Product.query.get(item['id'])
            if p and p.stock >= item['qty']:
                p.stock -= item['qty']
                total += p.price * item['qty']
            else: return jsonify({'success': False, 'message': 'Stock error'}), 400
        t = Transaction(total_amount=total, total_cost=total*0.7, status=method, customer_id=customer_id)
        db.session.add(t)
        db.session.commit()
        return jsonify({'success': True, 'transaction_id': t.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/receipt/<int:t_id>')
@login_required
def receipt(t_id):
    t = Transaction.query.get_or_404(t_id)
    return render_template('receipt.html', transaction=t, customer=t.customer, cart=[])

# ... (Standard Routes for Customers/Analysis assumed included or copied) ...
@app.route('/customers')
@login_required
def customers(): return render_template('customers.html', customers=Customer.query.all())

@app.route('/customer_form', methods=['GET', 'POST'])
@login_required
def customer_form():
    if request.method == 'POST':
        c = Customer(name=request.form.get('name'), phone=request.form.get('phone'), email=request.form.get('email'), address=request.form.get('address'))
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('customers'))
    return render_template('customer_form.html', title='Add Customer', customer=None)

@app.route('/analysis')
@login_required
def analysis():
    # Simplified analysis route
    return render_template('analysis.html', revenue=0, profit=0, cash_sales=0, card_sales=0, total_credit_due=0, loss_estimate=0, total_inventory_cost=0, dead_stock=[])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.first():
            user = User(username='admin')
            user.set_password('adminpass')
            db.session.add(user)
            db.session.commit()
    app.run(host='0.0.0.0', debug=True)