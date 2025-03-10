from flask import Flask, request, render_template, session, redirect, url_for, jsonify
import logging
import psycopg2 # type: ignore
from database import init_db, get_db_connection, put_db_connection, register_user, authenticate_user
from blockchain import Blockchain
from models import generate_keys, update_market_price, get_current_market_price, price_history, price_lock

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Initialize database and blockchain
init_db()
blockchain = Blockchain()

@app.route('/')
def home():
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        pub_key, priv_key = generate_keys()
        try:
            register_user(username, password, role, pub_key, priv_key)
            return "Registered successfully! <a href='/login'>Login here</a>"
        except psycopg2.IntegrityError:
            return "Username already exists!"
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = authenticate_user(username, password)
        if user:
            session['username'] = username
            session['role'] = user['role']
            logger.debug(f"User {username} logged in with role {user['role']}")
            return redirect(url_for('dashboard'))
        return "Invalid credentials!"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'producer':
        return redirect(url_for('producer_dashboard'))
    return redirect(url_for('buyer_dashboard'))

@app.route('/add_balance', methods=['GET', 'POST'])
def add_balance():
    if 'username' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    if request.method == 'POST':
        amount_str = request.form['amount']
        if not amount_str:
            return "Please enter an amount!"
        try:
            amount = float(amount_str)
            if amount <= 0:
                return "Amount must be positive!"
            blockchain.add_block({"type": "deposit", "username": session['username'], "amount": amount})
            return redirect(url_for('buyer_dashboard'))
        except ValueError:
            return "Invalid amount entered!"
    return render_template('add_balance.html')

@app.route('/producer_dashboard', methods=['GET', 'POST'])
def producer_dashboard():
    if 'username' not in session or session['role'] != 'producer':
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT tokens, balance FROM users WHERE username=%s", (session['username'],))
        result = c.fetchone()
        if result is None:
            logger.error(f"No user found for username: {session['username']}")
            return redirect(url_for('login'))
        tokens, balance = result
        if request.method == 'POST':
            energy_str = request.form['energy']
            if not energy_str:
                return "Please enter an energy amount!"
            try:
                energy = float(energy_str)
                if energy <= 0:
                    return "Energy must be positive!"
                blockchain.add_block({"type": "production", "username": session['username'], "energy": energy})
                update_market_price(energy, is_demand=False)
                c.execute("SELECT tokens, balance FROM users WHERE username=%s", (session['username'],))
                tokens, balance = c.fetchone()
                return redirect(url_for('producer_dashboard'))
            except ValueError:
                return "Invalid energy amount entered!"
        current_market_price = get_current_market_price()
        return render_template('producer_dashboard.html', username=session['username'], tokens=tokens, balance=balance, market_price=current_market_price)
    finally:
        put_db_connection(conn)

@app.route('/buyer_dashboard', methods=['GET', 'POST'])
def buyer_dashboard():
    if 'username' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT tokens, balance FROM users WHERE username=%s", (session['username'],))
        result = c.fetchone()
        if result is None:
            logger.error(f"No user found for username: {session['username']}")
            return redirect(url_for('login'))
        tokens, balance = result
        if request.method == 'POST':
            tokens_str = request.form['tokens']
            if not tokens_str:
                return "Please enter tokens to buy!"
            try:
                tokens_to_buy = float(tokens_str)
                if tokens_to_buy <= 0:
                    return "Tokens must be positive!"
                # Use the current market price at purchase time
                current_market_price = get_current_market_price()
                total_cost = tokens_to_buy * current_market_price
                logger.debug(f"Buying {tokens_to_buy} tokens at ₹{current_market_price}/token, total cost: ₹{total_cost}")
                if balance < total_cost:
                    return f"Insufficient balance! Need ₹{total_cost}, have ₹{balance}"
                c.execute("SELECT username FROM users WHERE role='producer' AND tokens >= %s LIMIT 1", (tokens_to_buy,))
                producer = c.fetchone()
                if producer:
                    producer_username = producer[0]
                    blockchain.add_block({"type": "transfer", "sender": producer_username, "recipient": session['username'],
                                         "tokens": tokens_to_buy, "price": current_market_price})
                    update_market_price(tokens_to_buy, is_demand=True)
                    c.execute("SELECT tokens, balance FROM users WHERE username=%s", (session['username'],))
                    tokens, balance = c.fetchone()
                else:
                    return "No producers with enough tokens available!"
                return redirect(url_for('buyer_dashboard'))
            except ValueError:
                return "Invalid tokens entered!"
        current_market_price = get_current_market_price()
        return render_template('buyer_dashboard.html', username=session['username'], tokens=tokens, balance=balance, market_price=current_market_price)
    finally:
        put_db_connection(conn)

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT data, timestamp FROM blockchain WHERE (data->>'username' = %s OR data->>'sender' = %s OR data->>'recipient' = %s) ORDER BY timestamp DESC",
                  (session['username'], session['username'], session['username']))
        transactions = c.fetchall()
        history = [{"data": row[0], "timestamp": row[1]} for row in transactions]
        return render_template('history.html', username=session['username'], history=history)
    finally:
        put_db_connection(conn)

@app.route('/price_data')
def price_data():
    with price_lock:
        logger.debug(f"Serving price_data: {price_history}")
        return jsonify(price_history)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    logger.debug(f"404 error: {request.url}")
    return "Page not found! Check the URL or go back to <a href='/login'>Login</a>", 404

if __name__ == "__main__":
    app.run(debug=True, threaded=True)