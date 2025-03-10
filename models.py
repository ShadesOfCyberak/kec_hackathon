from Crypto.PublicKey import RSA #type: ignore
from datetime import datetime
import threading

market_price = 5.0  # Starting price in INR per token
price_history = [{"time": datetime.now().strftime("%H:%M:%S"), "price": market_price}]
price_lock = threading.Lock()

def generate_keys():
    key = RSA.generate(2048)
    private_key = key.export_key().decode()
    public_key = key.publickey().export_key().decode()
    return public_key, private_key

def update_market_price(tokens, is_demand=True):
    global market_price, price_history
    with price_lock:
        adjustment = tokens * 0.001  # 0.1 INR per token unit
        if is_demand:
            market_price += adjustment
        else:
            market_price -= adjustment
        market_price = max(1.0, min(15.0, market_price))
        price_history.append({"time": datetime.now().strftime("%H:%M:%S"), "price": market_price})
        if len(price_history) > 10:
            price_history.pop(0)

def get_current_market_price():
    with price_lock:
        return market_price