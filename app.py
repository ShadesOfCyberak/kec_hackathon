from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import subprocess
import json
import logging
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FABRIC_CLIENT_PATH = os.path.join(BASE_DIR, 'fabric_client.js')

def run_fabric_command(func, args):
    cmd = ['node', FABRIC_CLIENT_PATH, func] + args
    logger.debug(f"Executing command: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.debug(f"stdout: {result.stdout}")
    logger.debug(f"stderr: {result.stderr}")
    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}: {result.stderr}")
        raise Exception(f"Command failed: {result.stderr}")
    if not result.stdout.strip():
        logger.error("No output from fabric_client.js")
        raise Exception("No output received from fabric_client.js")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}, raw output: {result.stdout}")
        raise

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        try:
            user_state = run_fabric_command("get_user_state", [username])
            if not user_state.get('payload') or not json.loads(user_state['payload']).get('username'):
                run_fabric_command("register_user", [username, role])
                logger.debug(f"Registered {username} as {role}")
                user_state = run_fabric_command("get_user_state", [username])
            session['username'] = username
            session['role'] = role
            return redirect(url_for('dashboard'))
        except Exception as e:
            return f"Error: {str(e)}"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session['role'] == 'producer':
        return redirect(url_for('producer_dashboard'))
    return redirect(url_for('buyer_dashboard'))

@app.route('/producer_dashboard', methods=['GET', 'POST'])
def producer_dashboard():
    if 'username' not in session or session['role'] != 'producer':
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'energy' in request.form:
            energy_str = request.form['energy']
            try:
                energy = float(energy_str)
                if energy <= 0:
                    return "Energy must be positive!"
                run_fabric_command("produce_energy", [session['username'], energy_str])
                return redirect(url_for('producer_dashboard'))
            except ValueError:
                return "Invalid energy amount!"
            except Exception as e:
                return f"Error: {str(e)}"
        elif 'withdraw_amount' in request.form:
            amount_str = request.form['withdraw_amount']
            try:
                amount = float(amount_str)
                if amount <= 0:
                    return "Amount must be positive!"
                run_fabric_command("withdraw_funds", [session['username'], amount_str])
                return redirect(url_for('producer_dashboard'))
            except ValueError:
                return "Invalid amount!"
            except Exception as e:
                return f"Error: {str(e)}"
    user_state_raw = run_fabric_command("get_user_state", [session['username']])
    user_state = json.loads(user_state_raw['payload']) if user_state_raw.get('payload') else {}
    market_price_raw = run_fabric_command("get_market_price", [])
    market_price = json.loads(market_price_raw['payload']) if market_price_raw.get('payload') else "5.0"
    return render_template('producer_dashboard.html', 
                          username=session['username'], 
                          tokens=user_state.get('tokens', 0.0), 
                          balance=user_state.get('balance', 0.0), 
                          market_price=market_price)

@app.route('/buyer_dashboard', methods=['GET', 'POST'])
def buyer_dashboard():
    if 'username' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'tokens' in request.form:
            tokens_str = request.form['tokens']
            try:
                tokens_to_buy = float(tokens_str)
                if tokens_to_buy <= 0:
                    return "Tokens must be positive!"
                producer = "producer1"  # Hardcoded for simplicity
                run_fabric_command("buy_tokens", [session['username'], producer, tokens_str])
                return redirect(url_for('buyer_dashboard'))
            except ValueError:
                return "Invalid tokens entered!"
            except Exception as e:
                return f"Error: {str(e)}"
        elif 'deposit_amount' in request.form:
            amount_str = request.form['deposit_amount']
            try:
                amount = float(amount_str)
                if amount <= 0:
                    return "Amount must be positive!"
                run_fabric_command("deposit_funds", [session['username'], amount_str])
                return redirect(url_for('buyer_dashboard'))
            except ValueError:
                return "Invalid amount!"
            except Exception as e:
                return f"Error: {str(e)}"
    user_state_raw = run_fabric_command("get_user_state", [session['username']])
    user_state = json.loads(user_state_raw['payload']) if user_state_raw.get('payload') else {}
    market_price_raw = run_fabric_command("get_market_price", [])
    market_price = json.loads(market_price_raw['payload']) if market_price_raw.get('payload') else "5.0"
    return render_template('buyer_dashboard.html', 
                          username=session['username'], 
                          tokens=user_state.get('tokens', 0.0), 
                          balance=user_state.get('balance', 0.0), 
                          market_price=market_price)

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))
    user_state_raw = run_fabric_command("get_user_state", [session['username']])
    user_state = json.loads(user_state_raw['payload']) if user_state_raw.get('payload') else {}
    return render_template('history.html', username=session['username'], history=[user_state])

@app.route('/price_data')
def price_data():
    market_price_raw = run_fabric_command("get_market_price", [])
    market_price = json.loads(market_price_raw['payload']) if market_price_raw.get('payload') else "5.0"
    return jsonify([{"time": "now", "price": float(market_price)}])

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == "__main__":
    try:
        subprocess.run(['node', FABRIC_CLIENT_PATH, 'register_user', 'admin', 'producer'], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass
    app.run(debug=True, host='0.0.0.0', port=5000)