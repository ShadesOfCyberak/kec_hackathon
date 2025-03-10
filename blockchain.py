from Crypto.Hash import SHA256 #type: ignore
import time
import json
import logging
from database import get_db_connection, put_db_connection

logger = logging.getLogger(__name__)

class Blockchain:
    def __init__(self):
        self.create_genesis_block()

    def create_genesis_block(self):
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM blockchain")
            if c.fetchone()[0] == 0:
                genesis_data = {"message": "Genesis Block"}
                genesis_hash = self.calculate_hash(0, "0", genesis_data)
                block = {"id": 0, "prev_hash": "0", "data": genesis_data, "timestamp": time.time(), "hash": genesis_hash}
                c.execute("INSERT INTO blockchain (prev_hash, data, timestamp, hash) VALUES (%s, %s, %s, %s)",
                          (block["prev_hash"], json.dumps(block["data"]), block["timestamp"], block["hash"]))
                conn.commit()
                logger.info("Genesis block created")
        finally:
            put_db_connection(conn)

    def calculate_hash(self, index, prev_hash, data):
        value = str(index) + prev_hash + json.dumps(data) + str(time.time())
        return SHA256.new(value.encode()).hexdigest()

    def add_block(self, data):
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT id, hash FROM blockchain ORDER BY id DESC LIMIT 1")
            prev_block = c.fetchone()
            prev_id, prev_hash = prev_block if prev_block else (0, "0")
            index = prev_id + 1
            block_hash = self.calculate_hash(index, prev_hash, data)
            block = {"id": index, "prev_hash": prev_hash, "data": data, "timestamp": time.time(), "hash": block_hash}
            c.execute("INSERT INTO blockchain (prev_hash, data, timestamp, hash) VALUES (%s, %s, %s, %s)",
                      (block["prev_hash"], json.dumps(block["data"]), block["timestamp"], block["hash"]))

            # Update tokens and balance based on transaction type
            if data["type"] == "production":
                c.execute("UPDATE users SET tokens = tokens + %s WHERE username=%s",
                          (data["energy"], data["username"]))
            elif data["type"] == "transfer":
                tokens = data["tokens"]
                total_cost = tokens * data["price"]
                c.execute("UPDATE users SET tokens = tokens - %s, balance = balance + %s WHERE username=%s",
                          (tokens, total_cost, data["sender"]))
                c.execute("UPDATE users SET tokens = tokens + %s, balance = balance - %s WHERE username=%s",
                          (tokens, total_cost, data["recipient"]))
            elif data["type"] == "deposit":
                c.execute("UPDATE users SET balance = balance + %s WHERE username=%s",
                          (data["amount"], data["username"]))
            conn.commit()
            logger.info(f"Block {index} added")
        finally:
            put_db_connection(conn)