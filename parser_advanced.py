import requests
import time
from datetime import datetime
import numpy as np

SERVER_URL = "https://ai-trade-machine.onrender.com/webhook"

def get_binance_klines(symbol, interval='1h', limit=100):
    """Получает свечи с Binance"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        closes = []
        highs = []
        lows = []
        volumes = []
        
        for candle in data:
            closes.append(float(candle[4]))
            highs.append(float(candle[2]))
            lows.append(float(candle[3]))
            volumes.append(float(candle[5]))
            
        return closes, highs, lows, volumes
    except:
        return [], [], [], []

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

def calculate_ema(closes, period):
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
    signal_line = ema_for_macd(closes[-signal:], signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram

def calculate_stochastic(closes, period=14):
    """Stochastic - момент импульса"""
    if len(closes) < period:
        return 50
    
    recent_closes = closes[-period:]
    lowest = min(recent_closes)
    highest = max(recent_closes)
    
    if highest == lowest:
        return 50
    
    return (closes[-1] - lowest) / (highest - lowest) * 100

def calculate_adx(highs, lows, closes, period=14):
    """ADX - сила тренда"""
    if len(closes) < period + 1:
        return 20
    
    plus_dm = []
    minus_dm = []
    tr = []
    
    for i in range(1, len(closes)):
        # True Range
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i-1])
        low_close = abs(lows[i] - closes[i-1])
        tr.append(max(high_low, high_close, low_close))
        
        # Directional Movement
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
            
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    
    # Сглаживание
    atr = sum(tr[-period:]) / period
    plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr if atr > 0 else 0
    minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr if atr > 0 else 0
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
    adx = dx  # упрощённо
    
    return adx, plus_di, minus_di

def check_ema_cross(ema10, ema20, ema50):
    """Проверяет пересечение EMA"""
    # BUY: EMA10 пересекает EMA20 снизу вверх И EMA20 выше EMA50
    if ema10 > ema20 and ema20 > ema50:
        return "bullish", "EMA: бычий порядок (10>20>50)"
    # SELL: EMA10 пересекает EMA20 сверху вниз И EMA20 ниже EMA50
    elif ema10 < ema20 and ema20 < ema50:
        return "bearish", "EMA: медвежий порядок (10<20<50)"
    else:
        return "neutral", "EMA: нет явного тренда"

def check_signal_multi_timeframe(symbol):
    """Проверяет сигнал на 3 таймфреймах"""
    
    timeframes = ['15m', '1h', '4h']
    signals = []
    
    for tf in timeframes:
        closes, highs, lows, volumes = get_binance_klines(symbol, tf, 100)
        if len(closes) < 50:
            continue
        
        # Базовые индикаторы
        rsi = calculate_rsi(closes)
        ema10 = calculate_ema(closes, 10)
        ema20 = calculate_ema(closes, 20)
        ema50 = calculate_ema(closes, 50)
        macd, macd_signal, macd_hist = calculate_macd(closes)
        stoch = calculate_stochastic(closes)
        adx, plus_di, minus_di = calculate_adx(highs, lows, closes)
        current_price = closes[-1]
        
        # Проверка EMA пересечений
        ema_trend, ema_reason = check_ema_cross(ema10, ema20, ema50)
        
        # Сила тренда (ADX > 25 значит сильный тренд)
        strong_trend = adx > 25
        
        # Подсчёт бычьих и медвежьих условий
        bullish_score = 0
        bearish_score = 0
        reasons = []
        
        # RSI
        if rsi < 35:
            bullish_score += 1
            reasons.append(f"RSI={rsi:.0f}")
        elif rsi > 70:
            bearish_score += 1
            reasons.append(f"RSI={rsi:.0f}")
        
        # EMA тренд
        if ema_trend == "bullish":
            bullish_score += 1
            reasons.append("EMA бычий")
        elif ema_trend == "bearish":
            bearish_score += 1
            reasons.append("EMA медвежий")
        
        # MACD
        if macd_hist > 0 and macd > macd_signal:
            bullish_score += 1
            reasons.append("MACD бычий")
        elif macd_hist < 0 and macd < macd_signal:
            bearish_score += 1
            reasons.append("MACD медвежий")
        
        # Stochastic
        if stoch < 30:
            bullish_score += 1
            reasons.append(f"Stoch={stoch:.0f}")
        elif stoch > 70:
            bearish_score += 1
            reasons.append(f"Stoch={stoch:.0f}")
        
        # ADX (сила тренда)
        if strong_trend:
            if plus_di > minus_di:
                bullish_score += 1
                reasons.append(f"ADX={adx:.0f} {plus_di:.0f}>{minus_di:.0f}")
            else:
                bearish_score += 1
                reasons.append(f"ADX={adx:.0f} {minus_di:.0f}>{plus_di:.0f}")
        
        # Решение по таймфрейму
        if bullish_score >= 3:
            signals.append(("buy", tf, reasons, current_price, rsi))
        elif bearish_score >= 3:
            signals.append(("sell", tf, reasons, current_price, rsi))
    
    # Агрегация по всем таймфреймам
    buy_signals = len([s for s in signals if s[0] == "buy"])
    sell_signals = len([s for s in signals if s[0] == "sell"])
    
    if buy_signals >= 2:
        return "buy", signals, buy_signals
    elif sell_signals >= 2:
        return "sell", signals, sell_signals
    else:
        return None, signals, 0

# АКТИВЫ ДЛЯ ОТСЛЕЖИВАНИЯ (50+)
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "UNIUSDT", "ATOMUSDT", "NEARUSDT", "OPUSDT",
    "ARBUSDT", "APTUSDT", "LTCUSDT", "BCHUSDT", "ETCUSDT",
    "XLMUSDT", "VETUSDT", "TRXUSDT", "EGLDUSDT", "THETAUSDT",
    "FILUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "AAVEUSDT",
    "ICPUSDT", "HBARUSDT", "FTMUSDT", "ALGOUSDT", "QNTUSDT"
]

def main():
    print("🤖 AI TRADE MACHINE - РАСШИРЕННЫЙ ПАРСЕР")
    print(f"📊 Отслеживаем {len(SYMBOLS)} активов")
    print(f"🎯 Индикаторы: RSI, EMA(10/20/50), MACD, Stochastic, ADX")
    print(f"⏰ Таймфреймы: 15m, 1h, 4h (сигнал при 2+ совпадениях)")
    print(f"🌐 Отправка на: {SERVER_URL}\n")
    
    while True:
        start_time = time.time()
        signals_sent = 0
        
        for symbol in SYMBOLS:
            try:
                action, tf_signals, count = check_signal_multi_timeframe(symbol)
                
                if action:
                    # Берём первый сигнал для цены и RSI
                    first_signal = tf_signals[0]
                    price = first_signal[3]
                    rsi = first_signal[4]
                    
                    # Формируем причину
                    all_reasons = []
                    for s in tf_signals:
                        reasons_str = ", ".join(s[2][:2])
                        all_reasons.append(f"{s[1]}({reasons_str})")
                    
                    reason = f"{action.upper()} сигнал на {count}/3 таймфреймах: " + " | ".join(all_reasons)
                    
                    webhook_data = {
                        "symbol": symbol,
                        "action": action,
                        "price": price,
                        "rsi": round(rsi, 1),
                        "reason": reason[:200]
                    }
                    
                    response = requests.post(SERVER_URL, json=webhook_data, timeout=10)
                    signals_sent += 1
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {symbol} → {action.upper()} | {reason[:80]}...")
                    
                time.sleep(0.5)  # пауза между активами
                
            except Exception as e:
                print(f"❌ Ошибка {symbol}: {e}")
        
        elapsed = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Цикл завершён | Сигналов: {signals_sent} | Время: {elapsed:.1f}с | Ожидание 30 сек...")
        time.sleep(30)

if __name__ == "__main__":
    main()