
from flask import Flask
import ccxt
import threading
import time
import requests
import pandas as pd
import pandas_ta as ta
from collections import deque
from config import BOT_TOKEN, CHAT_ID, PAIR_LIST

app = Flask(__name__)

# API URLs
NOBITEX_API = "https://api.nobitex.ir/market/stats"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# تاریخچه قیمت برای RSI
price_history = deque(maxlen=100)  # حدود 25 ساعت (اگر هر 15 دقیقه یک نمونه ذخیره شود)

# گرفتن قیمت‌ها از منابع مختلف
def fetch_price(symbol):
    try:
        if symbol == "TON/USDT":
            binance = ccxt.binance()
            ticker = binance.fetch_ticker("TON/USDT")
            return float(ticker['last'])
        elif symbol in ["TON/IRT", "USDT/IRT"]:
            res = requests.get(NOBITEX_API)
            data = res.json()
            key = symbol.lower().replace("/", "")
            return float(data["stats"][key]["latest"])
        elif symbol == "BTC/USDT":
            binance = ccxt.binance()
            ticker = binance.fetch_ticker("BTC/USDT")
            return float(ticker['last'])
        else:
            return None
    except Exception as e:
        print(f"خطا در دریافت قیمت {symbol}: {e}")
        return None

# محاسبه سیگنال اولیه آربیتراژ

def calculate_signal(prices):
    signal = ""
    try:
        ton_usdt = prices["TON/USDT"]
        ton_irt = prices["TON/IRT"]
        usdt_irt = prices["USDT/IRT"]

        implied_usdt_irt = ton_irt / ton_usdt
        diff_percent = ((implied_usdt_irt - usdt_irt) / usdt_irt) * 100

        signal += f"\U0001F4CA TON/USDT: {ton_usdt:.3f} $\n"
        signal += f"\U0001F4CA TON/IRT: {ton_irt:,.0f} تومان\n"
        signal += f"\U0001F4CA USDT/IRT: {usdt_irt:,.0f} تومان\n"
        signal += f"\U0001F4A1 Implied USDT/IRT via TON: {implied_usdt_irt:,.0f} تومان\n"
        signal += f"\U0001F4C8 اختلاف: {diff_percent:.2f}%\n"

        if diff_percent > 1.5:
            signal += "\n✅ فرصت فروش TON به ریال (قیمت بیش‌برآورد شده)"
        elif diff_percent < -1.5:
            signal += "\n✅ فرصت خرید TON به ریال (قیمت کم‌برآورد شده)"
        else:
            signal += "\nℹ️ وضعیت متعادل"

        return signal

    except Exception as e:
        return f"❗ خطا در تحلیل: {e}"

# محاسبه RSI

def calculate_rsi_signal():
    if len(price_history) < 20:
        return ""
    try:
        df = pd.DataFrame(price_history, columns=['close'])
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        if pd.isna(rsi):
            return ""
        if rsi < 30:
            return "\n📉 RSI پایین: احتمال رشد (خرید)"
        elif rsi > 70:
            return "\n📈 RSI بالا: احتمال اصلاح (فروش)"
        else:
            return f"\nℹ️ RSI فعلی: {rsi:.1f}"
    except Exception as e:
        return f"\n❗ خطا در محاسبه RSI: {e}"

# ارسال پیام تلگرام

def send_to_telegram(message):
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(TELEGRAM_API, data=payload)
    except Exception as e:
        print(f"❗ خطا در ارسال تلگرام: {e}")

# اجرای اصلی ربات

def run_bot():
    send_to_telegram("🚀 ربات تحلیلگر TON شروع به کار کرد!")
    while True:
        try:
            pair_list = PAIR_LIST + ["BTC/USDT"]
            prices = {pair: fetch_price(pair) for pair in pair_list}
            if all(prices.values()):
                price_history.append([prices["TON/USDT"]])
                signal = calculate_signal(prices)
                signal += calculate_rsi_signal()
                send_to_telegram(signal)
        except Exception as e:
            print(f"❗ خطای کلی: {e}")
        time.sleep(900)  # هر 15 دقیقه

# اطلاع‌رسانی هر 12 ساعت

def notify_every_12_hours():
    while True:
        time.sleep(43200)  # 12 ساعت
        send_to_telegram("🕒 ربات در حال اجراست و بدون مشکل کار می‌کند.")

# اجرای تردها
@app.before_request
def start_background_thread():
    if not hasattr(app, 'thread_started'):
        threading.Thread(target=run_bot, daemon=True).start()
        threading.Thread(target=notify_every_12_hours, daemon=True).start()
        app.thread_started = True

@app.route('/')
def index():
    return "✅ ربات تحلیلگر TON فعال است."

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
