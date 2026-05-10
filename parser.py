import requests
import time
from datetime import datetime

# Адрес твоего сервера
SERVER_URL = "https://ai-trade-machine.onrender.com/webhook"

def get_binance_klines(symbol, interval='1h'):
    """Получает свечи с Binance"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=100"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        closes = []
        volumes = []
        for candle in data:
            closes.append(float(candle[4]))
            volumes.append(float(candle[5]))
        return closes, volumes
    except:
        return [], []

def calculate_rsi(closes, period=14):
    """RSI - перекупленность/перепроданность"""
    if len(closes) < period + 1:
        return 50
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(closes, period=20):
    """EMA - экспоненциальная скользящая средняя"""
    if len(closes) < period:
        return closes[-1] if closes else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    
    for price in closes[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_macd(closes, fast=12, slow=26, signal=9):
    """MACD - трендовый индикатор"""
    if len(closes) < slow + signal:
        return 0, 0, 0
    
    def ema_for_macd(data, period):
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    macd_line = ema_for_macd(closes, fast) - ema_for_macd(closes, slow)
    signal_line = ema_for_macd(closes[-signal:], signal)  # упрощённо
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calculate_stochastic(closes, highs, lows, period=14):
    """Stochastic - момент импульса (упрощённо без highs/lows)"""
    if len(closes) < period:
        return 50
    
    recent_closes = closes[-period:]
    lowest = min(recent_closes)
    highest = max(recent_closes)
    
    if highest == lowest:
        return 50
    
    return (closes[-1] - lowest) / (highest - lowest) * 100

def calculate_obv(closes, volumes):
    """OBV - объём, подтверждающий тренд"""
    if len(closes) < 2 or len(volumes) < 2:
        return 0
    
    obv = 0
    for i in range(1, len(closes)):
        if closes[i] > closes[i-1]:
            obv += volumes[i]
        elif closes[i] < closes[i-1]:
            obv -= volumes[i]
    return obv

def check_signal(symbol):
    """Проверяет все индикаторы и принимает решение"""
    try:
        closes, volumes = get_binance_klines(symbol, '1h')
        if len(closes) < 50:
            return None
        
        # Расчёт всех индикаторов
        rsi = calculate_rsi(closes)
        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)
        macd, macd_signal, macd_hist = calculate_macd(closes)
        stoch = calculate_stochastic(closes, closes, closes)  # упрощённо
        obv = calculate_obv(closes, volumes)
        current_price = closes[-1]
        
        # Средний объём за последние 20 свечей
        avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else volumes[-1]
        volume_surge = volumes[-1] > avg_volume * 1.5
        
        # --- ЛОГИКА СИГНАЛА (комбинация индикаторов) ---
        reason = ""
        action = None
        
        # 🟢 СИГНАЛ НА ПОКУПКУ (LONG)
        buy_conditions = 0
        
        if rsi < 35:
            buy_conditions += 1
            reason += f"RSI={rsi:.0f} (низкий) "
        if current_price > ema20 and current_price > ema50:
            buy_conditions += 1
            reason += "цена выше EMA "
        if macd_hist > 0 and macd > macd_signal:
            buy_conditions += 1
            reason += "MACD бычий "
        if stoch < 30:
            buy_conditions += 1
            reason += "Stochastic перепродан "
        if volume_surge:
            reason += "объём вырос "
        
        if buy_conditions >= 3:
            action = "buy"
            reason = f"✅ {buy_conditions}/5 условий: " + reason
        
        # 🔴 СИГНАЛ НА ПРОДАЖУ (SHORT)
        sell_conditions = 0
        reason_sell = ""
        
        if rsi > 70:
            sell_conditions += 1
            reason_sell += f"RSI={rsi:.0f} (высокий) "
        if current_price < ema20 and current_price < ema50:
            sell_conditions += 1
            reason_sell += "цена ниже EMA "
        if macd_hist < 0 and macd < macd_signal:
            sell_conditions += 1
            reason_sell += "MACD медвежий "
        if stoch > 70:
            sell_conditions += 1
            reason_sell += "Stochastic перекуплен "
        
        if sell_conditions >= 3:
            action = "sell"
            reason = f"🔴 {sell_conditions}/5 условий: " + reason_sell
        
        # Отправка сигнала
        if action:
            webhook_data = {
                "symbol": symbol,
                "action": action,
                "price": current_price,
                "rsi": round(rsi, 1),
                "reason": reason.strip()
            }
            
            response = requests.post(SERVER_URL, json=webhook_data, timeout=10)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol} → {action.upper()} | RSI={rsi:.0f} | {reason[:80]}")
            return True
            
    except Exception as e:
        print(f"Ошибка {symbol}: {e}")
    
    return False

# 🔥 ТВОИ АКТИВЫ (те, что на сайте + популярные)
SYMBOLS = [
    # Криптовалюты
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "OPUSDT",
    "ARBUSDT", "APTUSDT", "LTCUSDT", "BCHUSDT", "ETCUSDT",
    "XLMUSDT", "VETUSDT", "TRXUSDT", "EGLDUSDT", "THETAUSDT",
    "FILUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "AAVEUSDT",
    
    # Форекс и сырьё (через Binance фьючерсы или другие API — позже)
    # Пока оставим крипту, так как Binance даёт просто API
]

def main():
    print("🤖 AI TRADE MACHINE - ПАРСЕР ЗАПУЩЕН")
    print(f"📊 Отслеживаем {len(SYMBOLS)} активов")
    print(f"🎯 Индикаторы: RSI, EMA(20/50), MACD, Stochastic, OBV, Volume")
    print(f"🌐 Отправка на: {SERVER_URL}\n")
    
    while True:
        start_time = time.time()
        signals_sent = 0
        
        for symbol in SYMBOLS:
            if check_signal(symbol):
                signals_sent += 1
            time.sleep(1)  # пауза между запросами
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Цикл завершён | Сигналов: {signals_sent} | Ожидание 60 сек...")
        time.sleep(60)  # раз в минуту

if __name__ == "__main__":
    main()