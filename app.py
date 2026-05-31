from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.base import AdminIndexView, expose

app = Flask(__name__)
app.secret_key = "secret_key"
from markupsafe import Markup

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '12345'
app.config['MYSQL_DB'] = 'ecommerce'

# SQLAlchemy for Flask-Admin
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:12345@localhost/ecommerce'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Init extensions
mysql = MySQL(app)
db = SQLAlchemy(app)

# Models
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)
    description = db.Column(db.Text)
    image = db.Column(db.String(200))

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(100))
    product_id = db.Column(db.Integer)
    quantity = db.Column(db.Integer)
    status = db.Column(db.String(50))
    order_date = db.Column(db.DateTime)

# Admin access control
class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if session.get('role') != 'admin':
            flash("Admin login required", "danger")
            return redirect(url_for('admin_login'))
        return super(MyAdminIndexView, self).index()

# Admin setup
admin = Admin(app, name='admin_dashboard', template_mode='', index_view=MyAdminIndexView())
admin.add_view(ModelView(Product, db.session))
admin.add_view(ModelView(User, db.session))
admin.add_view(ModelView(Order, db.session))

@app.route('/')
def home():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT p.*, SUM(o.quantity) AS total_sold
        FROM products p
        JOIN orders o ON p.id = o.product_id
        GROUP BY p.id
        ORDER BY total_sold DESC
        LIMIT 10
    """)
    recommended_products = cur.fetchall()
    return render_template('index.html', recommended=recommended_products)



@app.route('/products')
def products():
    search_query = request.args.get('query', '')

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if search_query:
        cur.execute("SELECT * FROM products WHERE name LIKE %s OR description LIKE %s", 
                    ('%' + search_query + '%', '%' + search_query + '%'))
    else:
        cur.execute("SELECT * FROM products")

    products = cur.fetchall()
    return render_template('product.html', products=products, search_query=search_query)


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'Janvier' and password == '12345':
            session['user'] = username
            session['role'] = 'admin'
            return redirect('/admin')
        else:
            flash('Invalid admin credentials', 'danger')

    return render_template('admin_login.html')

@app.route('/dashboard')
def admin_dashboard():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT COUNT(*) as total FROM products")
    total_products = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) as total FROM users")
    total_users = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) as total FROM orders")
    total_orders = cur.fetchone()['total']

    cur.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    status_counts = cur.fetchall()
    order_status_counts = {status['status']: status['count'] for status in status_counts}

    cur.execute("""
        SELECT o.id, o.user_email, p.name AS product_name, o.quantity,
               p.price, (p.price * o.quantity) AS total_price, o.status, o.order_date
        FROM orders o
        JOIN products p ON o.product_id = p.id
    """)
    orders = cur.fetchall()

    return render_template('admin_dashboard.html',
                           total_products=total_products,
                           total_users=total_users,
                           total_orders=total_orders,
                           pending_orders=order_status_counts.get('Pending', 0),
                           completed_orders=order_status_counts.get('Completed', 0),
                           shipped_orders=order_status_counts.get('Shipped', 0),
                           cancelled_orders=order_status_counts.get('Cancelled', 0),
                           orders=orders)
    
@app.route('/update_status/<int:order_id>', methods=['POST'])
def update_status(order_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    new_status = request.form.get('status')
    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
    mysql.connection.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and user['password'] == password:
            session['user'] = user['email']
            session['role'] = user.get('role', 'user')
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid credentials, please try again.")
    return render_template('login.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if user:
            return "User already exists", 409
        else:
            cur.execute("INSERT INTO users (email, password, role) VALUES (%s, %s, %s)", (email, password, 'user'))
            mysql.connection.commit()
            session['user'] = email
            session['role'] = 'user'
            return redirect(url_for('home'))
    return render_template('signin.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    session.pop('cart', None)
    return redirect(url_for('home'))

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    if 'cart' not in session:
        session['cart'] = {}

    cart = session['cart']
    if str(product_id) in cart:
        cart[str(product_id)] += 1
    else:
        cart[str(product_id)] = 1

    session['cart'] = cart
    session.modified = True
    return redirect(url_for('products'))

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('view_cart'))

    cur = mysql.connection.cursor()
    for product_id_str, quantity in cart.items():
        product_id = int(product_id_str)
        cur.execute("""
            INSERT INTO orders (user_email, product_id, quantity)
            VALUES (%s, %s, %s)
        """, (session['user'], product_id, quantity))
    mysql.connection.commit()

    # Clear the cart
    session.pop('cart', None)
    return render_template('order_success.html')


@app.route('/view_cart')
def view_cart():
    if 'user' not in session:
        return redirect(url_for('login'))

    cart = session.get('cart', {})

    if isinstance(cart, list):
        cart_dict = {}
        for pid in cart:
            pid_str = str(pid)
            cart_dict[pid_str] = cart_dict.get(pid_str, 0) + 1
        cart = cart_dict
        session['cart'] = cart
        session.modified = True

    products = []

    if cart:
        ids = list(map(int, cart.keys()))
        format_strings = ','.join(['%s'] * len(ids))
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", tuple(ids))
        fetched_products = cur.fetchall()

        for p in fetched_products:
            p['quantity'] = cart.get(str(p['id']), 0)
            products.append(p)

    return render_template('cart.html', cart=products)

@app.route('/update_quantity/<int:product_id>/<action>')
def update_quantity(product_id, action):
    cart = session.get('cart', {})
    product_key = str(product_id)

    if product_key in cart:
        if action == 'increase':
            cart[product_key] += 1
        elif action == 'decrease':
            cart[product_key] -= 1
            if cart[product_key] <= 0:
                cart.pop(product_key)

    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    product_key = str(product_id)

    if product_key in cart:
        cart.pop(product_key)

    session['cart'] = cart
    session.modified = True
    return redirect(url_for('view_cart'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        # You can store it in DB, send email, or just print for now
        print(f"New message from {name} ({email}): {message}")
        return render_template('contact_us.html', message_sent=True)
    return render_template('contact_us.html')

# Other routes like login, signin, logout, cart, etc. should be here (unchanged)
@app.route('/account')
def account():
    if 'user' not in session:
        return redirect(url_for('login'))

    user_email = session['user']
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Fetch user info
    cur.execute("SELECT * FROM users WHERE email = %s", (user_email,))
    user = cur.fetchone()

    # Fetch user's orders
    cur.execute("""
        SELECT o.id, p.name AS product_name, o.quantity,
               p.price, (p.price * o.quantity) AS total_price,
               o.status, o.order_date
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_email = %s
        ORDER BY o.order_date DESC
    """, (user_email,))
    orders = cur.fetchall()

    return render_template('account.html', user=user, orders=orders)

@app.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    # Only delete if the order belongs to the logged-in user
    cur.execute("DELETE FROM orders WHERE id = %s AND user_email = %s", (order_id, session['user']))
    mysql.connection.commit()

    return redirect(url_for('account'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user' not in session:
        return redirect(url_for('login'))

    email = session['user']

    cur = mysql.connection.cursor()
    # Delete user's orders first
    cur.execute("DELETE FROM orders WHERE user_email = %s", (email,))
    # Then delete user
    cur.execute("DELETE FROM users WHERE email = %s", (email,))
    mysql.connection.commit()

    session.clear()
    flash('Account deleted successfully!', 'success')
    return redirect(url_for('home'))
 
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_id = session['user_id']
    email = request.form['email']
    username = request.form['username']
    password = request.form['password']

    user = User.query.get(user_id)  # Get user from database

    user.email = email
    user.username = username

    if password:  # Only update if password is not empty
        user.set_password(password)  # Assuming you have a set_password() method to hash

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('account'))

@app.template_filter('highlight')
def highlight(text, search):
    if not search:
        return text
    highlighted = text.replace(search, f'<mark>{search}</mark>')
    return Markup(highlighted)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(debug=True)
