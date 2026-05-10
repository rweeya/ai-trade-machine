from flask import os import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('trading.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            action TEXT,
            price REAL,
            rsi REAL,
            ema REAL,
            volume REAL,
            reason TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("База данных создана с новыми колонками!")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signals')
def get_signals():
    conn = sqlite3.connect('trading.db')
    c = conn.cursor()
    try:
        c.execute('SELECT timestamp, symbol, action, price, rsi, ema, volume, reason FROM signals WHERE status = "active" ORDER BY timestamp DESC')
        rows = c.fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    
    signals = []
    for row in rows:
        signals.append({
            'timestamp': row[0],
            'symbol': row[1],
            'action': row[2],
            'price': row[3],
            'rsi': row[4] if row[4] else '-',
            'ema': row[5] if row[5] else '-',
            'volume': row[6] if row[6] else '-',
            'reason': row[7] if row[7] else '-'
        })
    return jsonify(signals)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    symbol = data.get('symbol')
    action = data.get('action')
    price = data.get('price', 0)
    rsi = data.get('rsi', 0)
    ema = data.get('ema', 0)
    volume = data.get('volume', 0)
    reason = data.get('reason', 'Сработала стратегия')
    
    conn = sqlite3.connect('trading.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO signals (timestamp, symbol, action, price, rsi, ema, volume, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), symbol, action, price, rsi, ema, volume, reason, 'active'))
    conn.commit()
    conn.close()
    print(f"Сигнал получен: {symbol} {action} RSI={rsi}")
    return 'ok'

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)

# Для Render
app = app