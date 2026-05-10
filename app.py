from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
import os

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
            reason TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signals')
def get_signals():
    conn = sqlite3.connect('trading.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, symbol, action, price, rsi, reason FROM signals WHERE status = "active" ORDER BY timestamp DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    
    signals = []
    for row in rows:
        signals.append({
            'timestamp': row[0],
            'symbol': row[1],
            'action': row[2],
            'price': row[3],
            'rsi': row[4] if row[4] else '-',
            'reason': row[5] if row[5] else '-'
        })
    return jsonify(signals)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        symbol = data.get('symbol', 'UNKNOWN')
        action = data.get('action', 'hold')
        price = data.get('price', 0)
        rsi = data.get('rsi', 0)
        reason = data.get('reason', 'Сигнал от TradingView')
        
        conn = sqlite3.connect('trading.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO signals (timestamp, symbol, action, price, rsi, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), symbol, action, price, rsi, reason, 'active'))
        conn.commit()
        conn.close()
        
        return 'ok', 200
    except Exception as e:
        print(f"Ошибка: {e}")
        return 'error', 500

# Создаём базу при первом запуске
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))