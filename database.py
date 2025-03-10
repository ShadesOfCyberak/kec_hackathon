import psycopg2 # type: ignore
from psycopg2 import pool # type: ignore
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

db_pool = None

def init_db():
    global db_pool
    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, 
                                                       dbname="energy_trading", 
                                                       user="energy_user", 
                                                       password="blockchain_energy", 
                                                       host="localhost")
        conn = db_pool.getconn()
        c = conn.cursor()
        # Use CREATE TABLE IF NOT EXISTS to avoid dropping existing tables
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                     id SERIAL PRIMARY KEY, 
                     username TEXT UNIQUE, 
                     password TEXT, 
                     pub_key TEXT, 
                     priv_key TEXT, 
                     tokens REAL DEFAULT 0, 
                     balance REAL DEFAULT 1000, 
                     role TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS blockchain (
                     id SERIAL PRIMARY KEY, 
                     prev_hash TEXT, 
                     data JSONB, 
                     timestamp REAL, 
                     hash TEXT)''')
        conn.commit()
        db_pool.putconn(conn)
        logger.info("Database initialized successfully")
    except psycopg2.Error as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise

def get_db_connection():
    if db_pool is None:
        raise RuntimeError("Database connection pool not initialized. Call init_db() first.")
    return db_pool.getconn()

def put_db_connection(conn):
    if db_pool is None:
        raise RuntimeError("Database connection pool not initialized.")
    db_pool.putconn(conn)

def register_user(username, password, role, pub_key, priv_key):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, pub_key, priv_key, tokens, balance, role) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                  (username, password, pub_key, priv_key, 0, 0, role))
        conn.commit()
        logger.info(f"User {username} registered successfully")
    except psycopg2.IntegrityError:
        logger.error(f"Username {username} already exists")
        raise
    finally:
        put_db_connection(conn)

def authenticate_user(username, password):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT role, pub_key, priv_key FROM users WHERE username=%s AND password=%s", (username, password))
        user = c.fetchone()
        if user:
            return {"role": user[0], "pub_key": user[1], "priv_key": user[2]}
        return None
    finally:
        put_db_connection(conn)